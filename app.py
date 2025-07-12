from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app) 

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservas.db'

app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

db = SQLAlchemy(app)
jwt = JWTManager(app)


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)


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
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)



with app.app_context():
    db.create_all()

    if not Usuario.query.filter_by(email="admin@lab.com").first():
        admin = Usuario(
            nome="Administrador",
            email="admin@lab.com",
            senha=generate_password_hash("12345678", method='pbkdf2:sha256'),
            tipo="admin"
        )
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado com sucesso!")
    else:
        print("Usuário admin já existe.")

    


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


def obter_proximas_datas(data_inicio, quantidade=3):
    proximas_datas = []
    
    try:
        data_atual = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError("O formato da data_inicio é inválido. Use o formato 'YYYY-MM-DDTHH:MM'.")
    
    for i in range(1, quantidade + 1):
        nova_data = data_atual + timedelta(days=7 * i)
        proximas_datas.append(nova_data)
    
    return proximas_datas


def existe_colisao(lab_id, inicio, fim, ignorar_reserva_id=None):
    query = Reserva.query.filter_by(laboratorio_id=lab_id)
    if ignorar_reserva_id:
        query = query.filter(Reserva.id != ignorar_reserva_id)

    for r in query.all():
        r_inicio = datetime.strptime(r.data_inicio, "%Y-%m-%dT%H:%M")
        r_fim    = datetime.strptime(r.data_fim,    "%Y-%m-%dT%H:%M")
        if not (fim <= r_inicio or inicio >= r_fim):
            return r  # retorna a reserva conflitante
    return None



@app.route('/api/usuarios', methods=['POST'])
@admin_required
def criar_usuario():
    data = request.get_json()
    nome = data.get('nome')
    email = data.get('email')
    senha = data.get('senha')
    tipo = data.get('tipo', 'professor')

    # Validação para garantir que o tipo de usuário seja apenas admin ou professor
    if tipo not in ['admin', 'professor']:
        return jsonify({'error': 'Tipo de usuário inválido'}), 400

    if not nome or not email or not senha:
        return jsonify({'error': 'Campos obrigatórios faltando'}), 400

    # Verificar se o email já existe
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'error': 'Email já cadastrado'}), 409

    # Gerar hash da senha
    senha_hash = generate_password_hash(senha, method='pbkdf2:sha256')

    novo_usuario = Usuario(nome=nome, email=email, senha=senha_hash, tipo=tipo)
    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({'message': 'Usuário criado com sucesso'}), 201



@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    senha = data.get('senha')

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not check_password_hash(usuario.senha, senha):
        return jsonify({'error': 'Credenciais inválidas'}), 401

    # Gerar o token de acesso
    access_token = create_access_token(identity=str(usuario.id))

    return jsonify({
        'token': access_token,
        'tipo': usuario.tipo,
        'nome': usuario.nome,
        'email': usuario.email
    }), 200



@app.route('/api/verificar_disponibilidade', methods=['POST'])
@jwt_required()
def verificar_disponibilidade():
    data_inicio = request.json.get('data_inicio')
    data_fim = request.json.get('data_fim')
    laboratorio_id = request.json.get('laboratorio_id')
    
    horario_inicio = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
    horario_fim = datetime.strptime(data_fim, "%Y-%m-%dT%H:%M")
    
    proximas_datas = obter_proximas_datas(data_inicio)

    reservas_existentes = Reserva.query.filter_by(laboratorio_id=laboratorio_id).all()

    datas_ocupadas = []
    datas_livres = []
    
    for data in proximas_datas:
        data_inicio_reserva = datetime.combine(data, datetime.min.time()) + timedelta(hours=horario_inicio.hour, minutes=horario_inicio.minute)
        data_fim_reserva = datetime.combine(data, datetime.min.time()) + timedelta(hours=horario_fim.hour, minutes=horario_fim.minute)
        
        ocupado = False
        for reserva in reservas_existentes:
            reserva_inicio = datetime.strptime(reserva.data_inicio, "%Y-%m-%dT%H:%M")
            reserva_fim = datetime.strptime(reserva.data_fim, "%Y-%m-%dT%H:%M")
            
            if not (data_fim_reserva <= reserva_inicio or data_inicio_reserva >= reserva_fim):
                ocupado = True
                break

        if ocupado:
            datas_ocupadas.append(data.strftime("%Y-%m-%dT%H:%M"))
        else:
            datas_livres.append(data.strftime("%Y-%m-%dT%H:%M"))
    

    return jsonify({
        'datas_ocupadas': datas_ocupadas,
        'datas_livres': datas_livres
    }), 200



@app.route('/api/minhas_reservas', methods=['GET'])
@jwt_required()
def minhas_reservas():
    usuario_id = get_jwt_identity()

    laboratorios = Laboratorio.query.all()
    reservas = Reserva.query.filter_by(usuario_id=usuario_id).all()

    laboratorios_reservas = {}

    for reserva in reservas:
        laboratorio_id = reserva.laboratorio_id
        if laboratorio_id not in laboratorios_reservas:
            laboratorios_reservas[laboratorio_id] = {
                'id': laboratorio_id,
                'nome': reserva.laboratorio.nome,
                'reservas': []
            }
        
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

    for laboratorio_id, laboratorio_info in laboratorios_reservas.items():
        laboratorio_info['reservas'] = sorted(
            laboratorio_info['reservas'], key=lambda x: datetime.strptime(x['data_inicio'], "%Y-%m-%dT%H:%M")
        )

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
    usuario_id = get_jwt_identity()
    reserva = Reserva.query.get(id)

    if not reserva:
        return jsonify({'msg': 'Reserva não encontrada'}), 404
    if int(reserva.usuario_id) != int(usuario_id):
        return jsonify({'msg': 'Você não tem permissão para editar esta reserva'}), 403

    # --- dados novos (ou antigos, se não enviados) ---------------------------
    data_inicio = request.json.get('data_inicio', reserva.data_inicio)
    data_fim    = request.json.get('data_fim',    reserva.data_fim)
    professor_responsavel = request.json.get(
        'professor_responsavel', reserva.professor_responsavel)
    num_estudantes = request.json.get('num_estudantes', reserva.num_estudantes)
    anotacoes      = request.json.get('anotacoes',      reserva.anotacoes)

    # --- validações de formato e ordem --------------------------------------
    try:
        data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
        data_fim_obj    = datetime.strptime(data_fim,    "%Y-%m-%dT%H:%M")
    except ValueError:
        return jsonify({'error': 'Formato de data inválido'}), 400

    if data_fim_obj <= data_inicio_obj:
        return jsonify({'error': 'A data de fim não pode ser anterior ou igual à data de início.'}), 400

    reservas_existentes = (Reserva.query
                           .filter_by(laboratorio_id=reserva.laboratorio_id)
                           .filter(Reserva.id != reserva.id)
                           .all())

    for r in reservas_existentes:
        r_inicio = datetime.strptime(r.data_inicio, "%Y-%m-%dT%H:%M")
        r_fim    = datetime.strptime(r.data_fim,    "%Y-%m-%dT%H:%M")

        if not (data_fim_obj <= r_inicio or data_inicio_obj >= r_fim):
            lab_nome = reserva.laboratorio.nome
            return jsonify({
                'error': f'O laboratório "{lab_nome}" já está reservado de '
                         f'{r_inicio.strftime("%H:%M")} às {r_fim.strftime("%H:%M")} nesse dia.'
            }), 400

    reserva.data_inicio = data_inicio
    reserva.data_fim    = data_fim
    reserva.professor_responsavel = professor_responsavel
    reserva.num_estudantes = num_estudantes
    reserva.anotacoes = anotacoes

    db.session.commit()
    return jsonify({'msg': 'Reserva atualizada com sucesso'}), 200




@app.route('/api/reserva/<int:id>', methods=['DELETE'])
@jwt_required()
def excluir_reserva(id):
    usuario_id = get_jwt_identity()

    reserva = Reserva.query.get(id)

    if not reserva:
        return jsonify({'msg': 'Reserva não encontrada'}), 404

    if int(reserva.usuario_id) != int(usuario_id):
        return jsonify({'msg': 'Você não tem permissão para editar esta reserva'}), 403

    db.session.delete(reserva)
    db.session.commit()

    return jsonify({'msg': 'Reserva excluída com sucesso'}), 200



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



@app.route('/api/laboratorio/<int:id>', methods=['PUT'])
@admin_required
def editar_laboratorio(id):
    data = request.get_json()
    nome = data.get('nome')
    local = data.get('local')

    laboratorio = Laboratorio.query.get(id)

    if not laboratorio:
        return jsonify({'error': 'Laboratório não encontrado'}), 404

    if nome:
        laboratorio.nome = nome
    if local:
        laboratorio.local = local

    db.session.commit()

    return jsonify({'message': 'Laboratório atualizado com sucesso'}), 200



@app.route('/api/laboratorio/<int:id>', methods=['DELETE'])
@admin_required
def excluir_laboratorio(id):
    laboratorio = Laboratorio.query.get(id)

    if not laboratorio:
        return jsonify({'msg': 'Laboratório não encontrado'}), 404

    try:
        Reserva.query.filter_by(laboratorio_id=id).delete()

        db.session.delete(laboratorio)
        db.session.commit()

        return jsonify({'msg': 'Laboratório excluído com sucesso!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Erro ao excluir laboratório', 'details': str(e)}), 500



@app.route('/api/add_reserva', methods=['POST'])
@jwt_required()
def api_add_reserva():
    reservas = request.get_json()
    usuario_id = get_jwt_identity()

    for reserva in reservas:
        data_inicio = reserva['data_inicio']
        data_fim = reserva['data_fim']
        professor_responsavel = reserva['professor_responsavel']
        num_estudantes = reserva['num_estudantes']
        repetir_horario = reserva['repetir_horario']
        anotacoes = reserva['anotacoes']
        laboratorio_id = reserva['laboratorio_id']
        datas_repetir = reserva.get('datas_repetir', [])

        try:
            data_inicio_obj = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
            data_fim_obj = datetime.strptime(data_fim, "%Y-%m-%dT%H:%M")
        except ValueError:
            return jsonify({'error': 'Formato de data inválido'}), 400

        if data_fim_obj <= data_inicio_obj:
            return jsonify({'error': 'A data de fim não pode ser anterior ou igual à data de início.'}), 400

        # 🔍 Verifica conflito
        conflito = existe_colisao(laboratorio_id, data_inicio_obj, data_fim_obj)
        if conflito:
            r_inicio = datetime.strptime(conflito.data_inicio, "%Y-%m-%dT%H:%M")
            r_fim = datetime.strptime(conflito.data_fim, "%Y-%m-%dT%H:%M")
            lab_nome = Laboratorio.query.get(laboratorio_id).nome
            return jsonify({
                'error': f'O "{lab_nome}" já está reservado de '
                         f'{r_inicio.strftime("%H:%M")} às {r_fim.strftime("%H:%M")} nesse dia.'
            }), 400

        # Criação da reserva principal
        nova_reserva = Reserva(
            data_inicio=data_inicio,
            data_fim=data_fim,
            professor_responsavel=professor_responsavel,
            num_estudantes=num_estudantes,
            repetir_horario=True,
            anotacoes=anotacoes,
            laboratorio_id=laboratorio_id,
            usuario_id=usuario_id
        )
        db.session.add(nova_reserva)

        # Se repetir, cria cópias nas datas informadas
        if repetir_horario and datas_repetir:
            duracao = data_fim_obj - data_inicio_obj

            for data in datas_repetir:
                data_inicio_repetida = datetime.strptime(data, "%Y-%m-%dT%H:%M")
                data_fim_repetida = data_inicio_repetida + duracao

                # 🔍 Verifica conflito para a reserva repetida
                conflito_repetida = existe_colisao(laboratorio_id, data_inicio_repetida, data_fim_repetida)
                if conflito_repetida:
                    r_inicio = datetime.strptime(conflito_repetida.data_inicio, "%Y-%m-%dT%H:%M")
                    r_fim = datetime.strptime(conflito_repetida.data_fim, "%Y-%m-%dT%H:%M")
                    lab_nome = Laboratorio.query.get(laboratorio_id).nome
                    return jsonify({
                        'error': f'Conflito na data repetida {data_inicio_repetida.strftime("%Y-%m-%d")}: '
                                 f'O laboratório "{lab_nome}" já está reservado de '
                                 f'{r_inicio.strftime("%H:%M")} às {r_fim.strftime("%H:%M")}.'
                    }), 400

                nova_reserva_repetida = Reserva(
                    data_inicio=data_inicio_repetida.strftime("%Y-%m-%dT%H:%M"),
                    data_fim=data_fim_repetida.strftime("%Y-%m-%dT%H:%M"),
                    professor_responsavel=professor_responsavel,
                    num_estudantes=num_estudantes,
                    repetir_horario=False,
                    anotacoes=anotacoes,
                    laboratorio_id=laboratorio_id,
                    usuario_id=usuario_id
                )
                db.session.add(nova_reserva_repetida)

    db.session.commit()
    return jsonify({'message': 'Reservas criadas com sucesso!'}), 201



if __name__ == "__main__":
    app.run(debug=True)
