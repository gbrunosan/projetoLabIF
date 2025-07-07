from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS  # Importar o CORS
from datetime import datetime

# Defina seus modelos e rotas abaixo


app = Flask(__name__)
CORS(app)  # Configura o CORS para permitir requisições de origens diferentes

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///reservas.db'  # Definindo o banco SQLite
db = SQLAlchemy(app)

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

# Inicializar o banco de dados
with app.app_context():
    db.create_all()

# Rota para retornar os laboratórios como JSON
@app.route('/api/laboratorios', methods=['GET'])
def api_laboratorios():
    laboratorios = Laboratorio.query.all()
    return jsonify([{
        'id': lab.id,
        'nome': lab.nome,
        'local': lab.local
    } for lab in laboratorios])

# Rota para retornar as reservas de um laboratório como JSON
@app.route('/api/laboratorio/<int:id>', methods=['GET'])
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



# Adicionar um novo Laboratório via API
@app.route('/api/add_laboratorio', methods=['POST'])
def api_add_laboratorio():
    try:
        data = request.get_json()
        nome = data['nome']
        local = data['local']
        
        novo_laboratorio = Laboratorio(nome=nome, local=local)
        db.session.add(novo_laboratorio)
        db.session.commit()
        
        return jsonify({'message': 'Laboratorio criado com sucesso!'}), 201  # Código 201 para sucesso
    except Exception as e:
        return jsonify({'error': 'Erro ao criar laboratorio', 'details': str(e)}), 500  # Se algo der errado



# Adicionar Nova Reserva via API
@app.route('/api/add_reserva', methods=['POST'])
def api_add_reserva():
    data = request.get_json()
    data_inicio = data['data_inicio']
    data_fim = data['data_fim']
    professor_responsavel = data['professor_responsavel']
    num_estudantes = data['num_estudantes']
    repetir_horario = data['repetir_horario']
    anotacoes = data['anotacoes']
    laboratorio_id = data['laboratorio_id']
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
        
        # Converte as datas recebidas para datetime
        nova_reserva_inicio = datetime.strptime(data_inicio, "%Y-%m-%dT%H:%M")
        nova_reserva_fim = datetime.strptime(data_fim, "%Y-%m-%dT%H:%M")

        # Verifica se há sobreposição de horários
        if (nova_reserva_inicio < reserva_fim and nova_reserva_fim > reserva_inicio):
            return jsonify({'error': 'Horário já ocupado!'}), 400  # Retorna erro se houver conflito

    # Criar a nova reserva se não houver conflito
    nova_reserva = Reserva(
        data_inicio=data_inicio, 
        data_fim=data_fim, 
        professor_responsavel=professor_responsavel,
        num_estudantes=num_estudantes, 
        repetir_horario=repetir_horario, 
        anotacoes=anotacoes,
        laboratorio_id=laboratorio_id
    )

    db.session.add(nova_reserva)
    db.session.commit()

    return jsonify({'message': 'Reserva criada com sucesso!'}), 201  # Código 201 para sucesso

# Rodar o servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
