from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Importar o CORS
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

app = Flask(__name__)
CORS(app) 

app.config['JWT_SECRET_KEY'] = '12345678secreto'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservas.db'

app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

db = SQLAlchemy(app)
jwt = JWTManager(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)  # Agora com hash
    tipo = db.Column(db.String(20), nullable=False)  # 'admin' ou 'comum'


# Modelo de Laboratório
class Laboratorio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    local = db.Column(db.String(100), nullable=False)
    reservas = db.relationship('Reserva', backref='laboratorio', lazy=True)

# Modelo de Reserva
class Reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_inicio = db.Column(db.String(50), nullable=False)
    data_fim = db.Column(db.String(50), nullable=False)
    professor_responsavel = db.Column(db.String(100), nullable=False)
    num_estudantes = db.Column(db.Integer, nullable=False)
    repetir_horario = db.Column(db.Boolean, default=False)
    anotacoes = db.Column(db.Text, nullable=True)
    laboratorio_id = db.Column(db.Integer, db.ForeignKey('laboratorio.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)  # Novo campo para associar à tabela de usuários


# Inicializar o banco de dados
with app.app_context():
    db.create_all()


def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        usuario = Usuario.query.get(user_id)

        if not usuario or usuario.tipo != 'admin':
            return jsonify({'error': 'Acesso restrito a administradores'}), 403

        return f(*args, **kwargs)
    return decorated


@app.route('/api/usuarios', methods=['POST'])
@admin_required
def criar_usuario():
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')
    tipo = data.get('tipo', 'professor')  # Tipo padrão é 'professor'

    # Validação para garantir que o tipo de usuário seja apenas admin ou professor
    if tipo not in ['admin', 'professor']:
        return jsonify({'error': 'Tipo de usuário inválido'}), 400

    if not nome or not email or not senha:
        return jsonify({'error': 'Campos obrigatórios faltando'}), 400

    # Verificar se o email já existe
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 409

    # Gerar hash da senha
    senha_hash = generate_password_hash(senha, method='sha256')

    # Criar o novo usuário com o tipo adequado
    novo_usuario = Usuario(nome=nome, email=email, senha=senha_hash, tipo=tipo)
    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({'message': 'Usuário criado com sucesso'}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')

    # Buscar o usuário pelo email
    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not check_password_hash(usuario.senha, senha):
        return jsonify({'error': 'Credenciais inválidas'}), 401  # Retorna erro se as credenciais não forem válidas

    # Gerar o token de acesso
    access_token = create_access_token(identity=str(usuario.id))

    # Retorna o token e informações do usuário
    return jsonify({
        'token': access_token,
        'tipo': usuario.tipo,
        'nome': usuario.nome,
        'email': usuario.email  # Agora também retorna o email
    }), 200


@app.route('/api/atualizar_senha', methods=['PUT'])
@jwt_required()
def atualizar_senha():
    data = request.get_json()
    nova_senha = data.get('nova_senha')
    usuario_id = get_jwt_identity()

    usuario = Usuario.query.get(usuario_id)

    if not usuario:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    # Atualiza a senha com hash
    usuario.senha = generate_password_hash(nova_senha, method='sha256')
    db.session.commit()

    return jsonify({'message': 'Senha atualizada com sucesso'}), 200

@app.route('/api/minhas_reservas', methods=['GET'])
@jwt_required()
def minhas_reservas():
    # Pega o ID do usuário logado a partir do token JWT
    usuario_id = get_jwt_identity()

    # Buscar os laboratórios e as reservas associadas ao usuário logado
    laboratorios = Laboratorio.query.all()  # Pegando todos os laboratórios
    reservas = Reserva.query.filter_by(usuario_id=usuario_id).all()  # Reservas do usuário

    # Criar um dicionário para armazenar reservas agrupadas por laboratório
    laboratorios_reservas = {}

    # Agrupar as reservas por laboratório
    for reserva in reservas:
        laboratorio_id = reserva.laboratorio_id
        if laboratorio_id not in laboratorios_reservas:
            laboratorios_reservas[laboratorio_id] = {
                'id': laboratorio_id,
                'nome': reserva.laboratorio.nome,  # Assumindo que o relacionamento está correto
                'reservas': []
            }
        
        # Adicionar a reserva à lista de reservas do respectivo laboratório
        laboratorios_reservas[laboratorio_id]['reservas'].append({
            'id': reserva.id,
            'data_inicio': reserva.data_inicio,
            'data_fim': reserva.data_fim,
            'professor_responsavel': reserva.professor_responsavel,
            'num_estudantes': reserva.num_estudantes,
            'repetir_horario': reserva.repetir_horario,
            'anotacoes': reserva.anotacoes,
            'laboratorio_id': reserva.laboratorio_id
        })

    # Converter o dicionário para uma lista de laboratórios
    laboratorios_formatados = list(laboratorios_reservas.values())

    return jsonify(laboratorios_formatados), 200



# Rota para retornar os laboratórios como JSON
@app.route('/api/laboratorios', methods=['GET'])
@jwt_required()
def api_laboratorios():
    laboratorios = Laboratorio.query.all()
    return jsonify([{
        'id': lab.id,
        'nome': lab.nome,
        'local': lab.local
    } for lab in laboratorios])

# Rota para retornar as reservas de um laboratório como JSON
@app.route('/api/laboratorio/<int:id>', methods=['GET'])
@jwt_required()
def api_laboratorio(id):
    laboratorio = Laboratorio.query.get_or_404(id)
    reservas = Reserva.query.filter_by(laboratorio_id=id).all()
    return jsonify([{
        'id': reserva.id,
        'data_inicio': reserva.data_inicio,
        'data_fim': reserva.data_fim,
        'professor_responsavel': reserva.professor_responsavel,
        'num_estudantes': reserva.num_estudantes,
        'repetir_horario': reserva.repetir_horario,
        'anotacoes': reserva.anotacoes
    } for reserva in reservas])

@app.route('/api/laboratorio/<int:id>/reservas', methods=['GET'])
@jwt_required()
def api_reservas_por_data(id):
    data = request.args.get('data')

    if not data:
        return jsonify({'error': 'Data não fornecida'}), 400

    data_formatada = datetime.strptime(data, "%Y-%m-%d").date()

    laboratorio = Laboratorio.query.get_or_404(id)

    reservas = Reserva.query.filter_by(laboratorio_id=id).all()

    reservas_filtradas = [
        reserva for reserva in reservas
        if datetime.strptime(reserva.data_inicio, "%Y-%m-%dT%H:%M").date() <= data_formatada <= datetime.strptime(reserva.data_fim, "%Y-%m-%dT%H:%M").date()
    ]

    return jsonify({
        'laboratorio': {
            'id': laboratorio.id,
            'nome': laboratorio.nome,
            'local': laboratorio.local
        },
        'reservas': [
            {
                'id': reserva.id,
                'data_inicio': reserva.data_inicio,
                'data_fim': reserva.data_fim,
                'professor_responsavel': reserva.professor_responsavel,
                'num_estudantes': reserva.num_estudantes,
                'repetir_horario': reserva.repetir_horario,
                'anotacoes': reserva.anotacoes
            } for reserva in reservas_filtradas
        ]
    })

@app.route('/api/reserva/<int:id>', methods=['PUT'])
@jwt_required()
def editar_reserva(id):
    # Pega o ID do usuário logado a partir do token JWT
    usuario_id = get_jwt_identity()

    # Buscar a reserva pelo ID
    reserva = Reserva.query.get(id)

    # Verificar se a reserva existe
    if not reserva:
        return jsonify({'msg': 'Reserva não encontrada'}), 404
    # Verificar se a reserva pertence ao usuário logado
    if int(reserva.usuario_id) != int(usuario_id):  # Força ambos os IDs a serem inteiros
        return jsonify({'msg': 'Você não tem permissão para editar esta reserva'}), 403


    # Obter os dados da reserva do corpo da requisição
    data_inicio = request.json.get('data_inicio', reserva.data_inicio)
    data_fim = request.json.get('data_fim', reserva.data_fim)
    professor_responsavel = request.json.get('professor_responsavel', reserva.professor_responsavel)
    num_estudantes = request.json.get('num_estudantes', reserva.num_estudantes)
    anotacoes = request.json.get('anotacoes', reserva.anotacoes)

    # Atualizar a reserva com os novos dados
    reserva.data_inicio = data_inicio
    reserva.data_fim = data_fim
    reserva.professor_responsavel = professor_responsavel
    reserva.num_estudantes = num_estudantes
    reserva.anotacoes = anotacoes

    # Commitando as mudanças no banco
    db.session.commit()

    return jsonify({'msg': 'Reserva atualizada com sucesso'}), 200



# Rota para excluir uma reserva
@app.route('/api/reserva/<int:id>', methods=['DELETE'])
@jwt_required()
def excluir_reserva(id):
    # Pega o ID do usuário logado a partir do token JWT
    usuario_id = get_jwt_identity()

    # Buscar a reserva pelo ID
    reserva = Reserva.query.get(id)

    # Verificar se a reserva existe
    if not reserva:
        return jsonify({'msg': 'Reserva não encontrada'}), 404

    # Verificar se a reserva pertence ao usuário logado
    if int(reserva.usuario_id) != int(usuario_id):  # Força ambos os IDs a serem inteiros
        return jsonify({'msg': 'Você não tem permissão para editar esta reserva'}), 403

    # Excluir a reserva
    db.session.delete(reserva)
    db.session.commit()

    return jsonify({'msg': 'Reserva excluída com sucesso'}), 200

# Adicionar um novo Laboratório via API
@app.route('/api/add_laboratorio', methods=['POST'])
@admin_required
def api_add_laboratorio():
    try:
        data = request.get_json()
        nome = data['nome']
        local = data['local']
        
        novo_laboratorio = Laboratorio(nome=nome, local=local)
        db.session.add(novo_laboratorio)
        db.session.commit()
        
        return jsonify({'message': 'Laboratório criado com sucesso!'}), 201
    except Exception as e:
        return jsonify({'error': 'Erro ao criar laboratório', 'details': str(e)}), 500



@app.route('/api/add_reserva', methods=['POST'])
@jwt_required()
def api_add_reserva():
    data = request.get_json()
    data_inicio = data['data_inicio']
    data_fim = data['data_fim']
    professor_responsavel = data['professor_responsavel']
    num_estudantes = data['num_estudantes']
    repetir_horario = data['repetir_horario']
    anotacoes = data['anotacoes']
    laboratorio_id = data['laboratorio_id']
    
    usuario_id = get_jwt_identity()  # Recupera o ID do usuário logado

    # Converte as datas recebidas para datetime
    nova_reserva_inicio = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
    nova_reserva_fim = datetime.strptime(data_fim, "%Y-%m-%dT%H:%M")

    # ✅ Valida se a data de fim é depois da data de início
    if nova_reserva_fim <= nova_reserva_inicio:
        return jsonify({'error': 'Data/hora final deve ser posterior à inicial'}), 400

    # Verificar se a nova reserva se sobrepõe com alguma reserva existente
    reservas_existentes = Reserva.query.filter_by(laboratorio_id=laboratorio_id).all()
    
    for reserva in reservas_existentes:
        reserva_inicio = datetime.strptime(reserva.data_inicio, "%Y-%m-%dT%H:%M")
        reserva_fim = datetime.strptime(reserva.data_fim, "%Y-%m-%dT%H:%M")

        # Verifica se há sobreposição de horários
        if (nova_reserva_inicio < reserva_fim and nova_reserva_fim > reserva_inicio):
            return jsonify({'error': 'Horário já ocupado!'}), 400  # Retorna erro se houver conflito

    # Criar a nova reserva associada ao usuário logado
    nova_reserva = Reserva(
        data_inicio=data_inicio, 
        data_fim=data_fim, 
        professor_responsavel=professor_responsavel,
        num_estudantes=num_estudantes, 
        repetir_horario=repetir_horario, 
        anotacoes=anotacoes,
        laboratorio_id=laboratorio_id,
        usuario_id=usuario_id  # Associando a reserva ao usuário logado
    )

    db.session.add(nova_reserva)
    db.session.commit()

    return jsonify({'message': 'Reserva criada com sucesso!'}), 201  # Código 201 para sucesso


# Rodar o servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
