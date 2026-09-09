from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
import bcrypt
from database import db_conexao

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Decorator para perfil admin na API
def admin_api_required():
    def wrapper(fn):
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            if claims.get("tipo") != "admin":
                return jsonify({"erro": "Acesso restrito a administradores"}), 403
            return fn(*args, **kwargs)
        decorator.__name__ = fn.__name__
        return decorator
    return wrapper

# --- AUTENTICAÇÃO ---

@api_bp.route('/login', methods=['POST', 'GET'])
def api_login():
    dados = request.get_json() or {}
    usuario_digitado = dados.get('email')
    senha_digitada = dados.get('senha')

    if not usuario_digitado or not senha_digitada:
        return jsonify({'erro': 'Usuário e senha são obrigatórios'}), 400

    conn = db_conexao()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (usuario_digitado,))
        usuario = cursor.fetchone()

        if usuario and bcrypt.checkpw(senha_digitada.encode('utf-8'), usuario['senha'].encode('utf-8')):
            token = create_access_token(
                identity=str(usuario['email']),
                additional_claims={'email': usuario['email'], 'tipo': usuario['tipo']}
            )
            return jsonify({
                'sucesso': True,
                'token': token,
                'usuario': {
                    'email': usuario['email'],
                    'tipo': usuario['tipo']
                }
            }), 200
        return jsonify({'erro': 'Credenciais inválidas'}), 401
    finally:
        cursor.close()
        conn.close()

# --- ITENS E ESTOQUE ---

@api_bp.route('/itens', methods=['GET'])
@jwt_required()
def api_listar_itens():
    conn = db_conexao()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM itens")
        itens = cursor.fetchall()
        return jsonify({'itens': itens}), 200
    finally:
        cursor.close()
        conn.close()

@api_bp.route('/item/<int:id_item>', methods=['GET'])
@jwt_required()
def api_buscar_item(id_item):
    conexao = db_conexao()
    cursor = conexao.cursor(dictionary=True)

    try:
        cursor.execute("SELECT nome, quantidade, estoque_min FROM itens WHERE id = %s", (id_item,))
        item = cursor.fetchone()

        if not item:
            return jsonify({'erro': 'Item não encontrado'}), 404     

        cursor.execute(
            "SELECT tipo, pessoa, destino, DATE_FORMAT(data, '%d/%m/%Y %H:%i') as data FROM historico WHERE id_item = %s ORDER BY data DESC", 
            (id_item,)
        )
        historico = cursor.fetchall()

        return jsonify({
            'nome': item['nome'],
            'quantidade': item['quantidade'],
            'estoque_min': item['estoque_min'],
            'historico': historico
        }), 200
    finally:
        cursor.close()
        conexao.close()

@api_bp.route('/movimentar', methods=['POST'])
@jwt_required()
def api_movimentar_item():
    dados = request.get_json() or {}
    id_item = dados.get('id') or dados.get('itemId')
    quantidade_nova = dados.get('quantidade') or dados.get('novaQuantidade')
    pessoa = dados.get('pessoa')
    destino = dados.get('destino')
    tipo = dados.get('tipo')

    conexao = db_conexao()
    cursor = conexao.cursor()

    try:
        cursor.execute("UPDATE itens SET quantidade = %s WHERE id = %s", (quantidade_nova, id_item))
        cursor.execute("INSERT INTO historico (id_item, tipo, pessoa, destino, data) VALUES (%s, %s, %s, %s, NOW())", (id_item, tipo, pessoa, destino))

        conexao.commit()
        return jsonify({'sucesso': True}), 200
    except Exception as e:
        conexao.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500
    finally:
        cursor.close()
        conexao.close()

# --- USUÁRIOS ---

@api_bp.route('/usuarios', methods=['POST'])
@admin_api_required()
def api_cadastrar_usuario():
    dados = request.get_json() or {}
    email = (dados.get('email') or '').strip()
    senha = (dados.get('senha') or '').strip()
    tipo = (dados.get('posto') or 'comum').strip().lower()

    if not email or not senha:
        return jsonify({'erro': 'Preencha todos os campos'}), 400

    senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    conn = db_conexao()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (email, senha, tipo) VALUES (%s, %s, %s);', (email, senha_hash, tipo))
        conn.commit()
        return jsonify({'sucesso': True, 'mensagem': 'Usuário cadastrado com sucesso!'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'erro': 'Erro ao cadastrar usuário'}), 400
    finally:
        cursor.close()
        conn.close()