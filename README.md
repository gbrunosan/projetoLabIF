# Back-End - Projeto de Reservas de Laboratórios IFMS

Este é o back-end da aplicação de reservas de laboratórios para o **IFMS**. A API permite que os usuários façam reservas, editem, excluam e visualizem laboratórios e horários disponíveis.

## Tecnologias Utilizadas

- **Flask**: Framework web para Python, usado para construir a API.
- **Flask-SQLAlchemy**: Para integração com o banco de dados.
- **Flask-JWT-Extended**: Para autenticação via tokens.
- **Flask-CORS**: Para permitir que o front-end se comunique com o back-end de diferentes origens (CORS).
- **Werkzeug**: Biblioteca de utilitários para segurança (hashing de senhas).
- **python-dotenv**: Para carregar variáveis de ambiente a partir de um arquivo `.env`.

## Como Executar o Projeto

Eu coloquei uma chave no env para ser usada na geração de tokens, se usado em produção alterem essa chave no env já que ele essa está pública.

```bash
# O tempo de duração de um token para manter um usuário logado também é alterável nessa linha
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)


# Clone o repositório para sua máquina local:
git clone https://github.com/gbrunosan/projetoLabIF
cd projetoLabIF


## Inicie o ambiente
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate


## Instale as depêndencias
pip install -r requirements.txt

## Inicie o servidor
python app.py
```