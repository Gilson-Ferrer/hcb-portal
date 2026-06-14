import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, session, flash, jsonify
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import io
from flask import send_file, jsonify, request, session
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

EVENT_END = datetime(2026, 6, 8, 23, 59, 59)

app = Flask(__name__)

# Configuração de chaves e banco para testes locais
app.secret_key = os.environ.get('SECRET_KEY', 'asyncx_hack_2026_local_key')
DATABASE_URL = os.environ.get('DATABASE_URL')

# ==============================================================================
# INTELIGÊNCIA MULTI-TENANT (O SEGREDO DA ESCALABILIDADE)
# ==============================================================================
# Localmente você pode alterar essa variável para testar outras faculdades (ex: 'anhanguera')
TENANT_ID = os.environ.get('TENANT_ID', 'estacio')
INSTITUTION_NAME = os.environ.get('INSTITUTION_NAME', 'ESTÁCIO CARAPICUÍBA')

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def get_event_details(cur):
    """Busca os detalhes do evento atual diretamente do banco de dados"""
    cur.execute('SELECT * FROM tenants WHERE id = %s AND is_active = TRUE', (TENANT_ID,))
    return cur.fetchone()

@app.route('/')
def index():
    if 'team_id' in session: 
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form['name']
    password = request.form['password']
    
    conn = get_db()
    cur = conn.cursor()
    
    # Blinda o login para garantir que o time pertence a esta unidade/faculdade
    cur.execute('''
        SELECT * FROM teams 
        WHERE name = %s AND password = %s AND tenant_id = %s
    ''', (name, password, TENANT_ID))
    team = cur.fetchone()
    cur.close()
    conn.close()
    
    if team:
        session['team_id'] = team['id']
        session['team_name'] = team['name']
        session['tenant_id'] = TENANT_ID
        return redirect('/dashboard')
        
    flash("Credenciais Incorretas ou time não cadastrado nesta unidade.", "danger")
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'team_id' not in session: 
        return redirect('/')
        
    conn = get_db()
    cur = conn.cursor()
    
    # Busca dados do evento
    event = get_event_details(cur)
    if not event:
        cur.close()
        conn.close()
        return "Este evento não está ativo.", 404

    # === 1. NOVO: BUSCA O AVATAR DA EQUIPE LOGADA ===
    cur.execute('SELECT avatar_url FROM teams WHERE id = %s', (session['team_id'],))
    current_team = cur.fetchone()

    # === ATUALIZADO: BUSCA AVATAR E INTEGRANTES DA EQUIPE LOGADA ===
    cur.execute('SELECT score, avatar_url, members FROM teams WHERE id = %s', (session['team_id'],))
    current_team = cur.fetchone()
    # Se o avatar for nulo no banco, define 'default.webp' como padrão
    team_avatar = current_team['avatar_url'] if current_team and current_team['avatar_url'] else 'default.webp'
    # ================================================
    team_members = current_team['members'] if current_team and current_team['members'] else ""
    # ==============================================================
    # Busca todos os times para a matriz (Ranking isolado por faculdade)
    cur.execute('SELECT id, name, score FROM teams WHERE tenant_id = %s ORDER BY score DESC, last_solve ASC', (TENANT_ID,))
    all_teams = cur.fetchall()

    # Busca todos os desafios desta faculdade
    cur.execute('SELECT * FROM challenges WHERE tenant_id = %s ORDER BY id ASC', (TENANT_ID,))
    all_challenges = cur.fetchall()
    
    # Busca todos os solves para montar a matriz
    cur.execute('SELECT team_id, challenge_id FROM solves')
    all_solves = cur.fetchall()
    solves_matrix = {}
    for s in all_solves:
        if s['team_id'] not in solves_matrix: solves_matrix[s['team_id']] = set()
        solves_matrix[s['team_id']].add(s['challenge_id'])
    
    # Organiza desafios por categoria
    categories = ['Cyberdetective', 'Invasion', 'Defense', 'Code', 'Arcade', 'Hardware']
    challenges_by_category = {cat: [] for cat in categories}
    for c in all_challenges:
        cat = c.get('category', 'Cyberdetective')
        if cat in challenges_by_category:
            challenges_by_category[cat].append(c)

    # Mapeia resoluções e dicas do time logado
    cur.execute('SELECT challenge_id FROM solves WHERE team_id = %s', (session['team_id'],))
    solved_ids = [row['challenge_id'] for row in cur.fetchall()]
    cur.execute('SELECT challenge_id FROM hint_purchases WHERE team_id = %s', (session['team_id'],))
    purchased_ids = [row['challenge_id'] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', 
                           event_name=event['name'],
                           all_teams=all_teams, 
                           all_challenges=all_challenges, 
                           solves_matrix=solves_matrix, 
                           challenges_by_category=challenges_by_category, 
                           solved_ids=solved_ids, 
                           purchased_ids=purchased_ids,
                           ranking=all_teams, 
                           team_avatar=team_avatar,
                           institution_name=INSTITUTION_NAME,
                           team_members=team_members,
                           end_time=event['end_time'].isoformat())

@app.route('/leaderboard')
def leaderboard():
    conn = get_db()
    cur = conn.cursor()
    
    # ADICIONEI O 'score' NA CONSULTA ABAIXO
    cur.execute('SELECT id, name, score FROM teams WHERE tenant_id = %s ORDER BY score DESC, name ASC', (TENANT_ID,))
    all_teams = cur.fetchall()
    
    cur.execute('SELECT * FROM challenges WHERE tenant_id = %s ORDER BY id ASC', (TENANT_ID,))
    all_challenges = cur.fetchall()
    
    cur.execute('SELECT team_id, challenge_id FROM solves')
    all_solves = cur.fetchall()
    solves_matrix = {}
    for s in all_solves:
        if s['team_id'] not in solves_matrix: solves_matrix[s['team_id']] = set()
        solves_matrix[s['team_id']].add(s['challenge_id'])

    # Busca tempo final para o timer
    cur.execute('SELECT end_time FROM tenants WHERE id = %s', (TENANT_ID,))
    event = cur.fetchone()
    
    cur.close()
    conn.close()
    
    return render_template('leaderboard_public.html', 
                           all_teams=all_teams, 
                           all_challenges=all_challenges, 
                           solves_matrix=solves_matrix,
                           end_time=event['end_time'].isoformat())

@app.route('/hint/<int:id>')
def get_hint(id):
    if 'team_id' not in session: 
        return "Acesso negado", 403
        
    conn = get_db()
    cur = conn.cursor()
    
    event = get_event_details(cur)
    if not event or (event['end_time'] and datetime.now() > event['end_time']):
        cur.close()
        conn.close()
        return jsonify({"hint": "O evento terminou! Submissões trancadas.", "error": True})

    # Verifica se a dica já foi comprada anteriormente
    cur.execute('SELECT 1 FROM hint_purchases WHERE team_id = %s AND challenge_id = %s', 
                (session['team_id'], id))
    if cur.fetchone():
        cur.execute('SELECT hint FROM challenges WHERE id = %s', (id,))
        hint = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify({"hint": hint['hint']})

    # Debita a pontuação da carteira do time (-25 pontos)
    cur.execute('UPDATE teams SET score = score - 25 WHERE id = %s', (session['team_id'],))
    cur.execute('INSERT INTO hint_purchases (team_id, challenge_id) VALUES (%s, %s)', 
                (session['team_id'], id))
    conn.commit()
    
    cur.execute('SELECT hint FROM challenges WHERE id = %s', (id,))
    hint = cur.fetchone()
    cur.close()
    conn.close()
    
    return jsonify({"hint": hint['hint']})

@app.route('/submit', methods=['POST'])
def submit():
    if 'team_id' not in session: 
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()
    
    event = get_event_details(cur)
    if not event or (event['end_time'] and datetime.now() > event['end_time']):
        cur.close()
        conn.close()
        flash("O evento terminou! Submissões encerradas.", "danger")
        return redirect('/dashboard')

    challenge_id = request.form.get('challenge_id')
    flag = request.form['flag'].strip()
    
    # Valida a flag batendo contra o ID do desafio e garantindo o tenant correto
    cur.execute('SELECT * FROM challenges WHERE id = %s AND flag = %s AND tenant_id = %s', 
                (challenge_id, flag, TENANT_ID))
    challenge = cur.fetchone()
    
    if challenge:
        cur.execute('SELECT * FROM solves WHERE team_id = %s AND challenge_id = %s', 
                    (session['team_id'], challenge['id']))
        if not cur.fetchone():
            cur.execute('INSERT INTO solves (team_id, challenge_id) VALUES (%s, %s)', 
                        (session['team_id'], challenge['id']))
            
            agora = datetime.now()
            cur.execute('UPDATE teams SET score = score + %s, last_solve = %s WHERE id = %s', 
                        (challenge['points'], agora, session['team_id']))
            conn.commit()
            flash("Flag correta! Sistema atualizado.", "success")
    else:
        flash("Flag incorreta! Vetor de ataque rejeitado.", "danger")
        
    cur.close()
    conn.close()
    return redirect('/dashboard')

@app.route('/update_avatar', methods=['POST'])
def update_avatar():
    if 'team_id' not in session:
        return jsonify({"success": False, "message": "Não autorizado"}), 403
    
    data = request.get_json()
    avatar_name = data.get('avatar_name')
    
    conn = get_db()
    cur = conn.cursor()
    # Atualiza a coluna avatar_url na tabela teams
    cur.execute('UPDATE teams SET avatar_url = %s WHERE id = %s', 
                (avatar_name, session['team_id']))
    conn.commit()
    cur.close()
    conn.close()

    session['team_avatar'] = avatar_name    
    return jsonify({"success": True})

@app.route('/generate_certificate', methods=['POST'])
def generate_certificate():
    if 'team_id' not in session:
        return "Não autorizado", 403
        
    member_name = request.form.get('member_name')
    if not member_name:
        return "Nome do integrante inválido", 400

    conn = get_db()
    cur = conn.cursor()
    
    event = get_event_details(cur)
    cur.close()
    conn.close()
    
    if not event:
        return "Evento não configurado", 404

    # =========================================================================
    # 🔒 BLOCKER TEMPORAL: Impede a emissão antes do término do evento
    # =========================================================================

    # Captura a hora exata no fuso de São Paulo, ignorando o relógio do Servidor
    fuso_br = ZoneInfo('America/Sao_Paulo')
    agora = datetime.now(fuso_br)
    
    # Como a data que vem do banco (Postgres) geralmente é "naive" (sem fuso),
    # precisamos dizer ao Python que aquela data do banco também é do Brasil:
    end_time_banco = event['end_time'].replace(tzinfo=fuso_br)

    if agora < end_time_banco:
        return "Acesso Negado: A emissão do certificado só estará disponível após o encerramento oficial do evento.", 403

    # =========================================================================
    # 1. ENGENHARIA DE DADOS CRONOLÓGICOS E INSTITUCIONAIS (DINÂMICOS)
    # =========================================================================
    event_title = event['name']                           # Ex: "Hackathon Estácio 2026"
    inst_name = INSTITUTION_NAME                          # Ex: "ESTÁCIO CARAPICUÍBA"
    
    # Regra de Negócio: O evento dura 3 dias e termina no end_time
    end_date = event['end_time']
    start_date = end_date - timedelta(days=2)             # Subtrai 2 dias para pegar o dia de início
    
    # --- DICIONÁRIO DE TRADUÇÃO DOS MESES (Mapeamento Base-Zero para o Servidor) ---

    meses_pt = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
            5: "maio", 6: "junho", 7: "julho", 8: "agosto",
            9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
        }
    
    # Captura o número do mês (end_date.month retorna um inteiro de 1 a 12)
    month_name = meses_pt.get(end_date.month)
    year_name = end_date.strftime('%Y')
    
    # Monta a string perfeitamente em português nativo
    date_range_str = f"no período de {start_date.day} a {end_date.day} de {month_name} de {year_name}"

    # =========================================================================
    # 2. LEITURA DINÂMICA DAS DIMENSÕES DO SEU CERTIFICADO PREFERIDO
    # =========================================================================
    template_path = os.path.join(app.root_path, 'static', 'materials', 'certificate_background.pdf')
    
    try:
        existing_pdf = PdfReader(open(template_path, "rb"))
        page = existing_pdf.pages[0]
    except FileNotFoundError:
        return "Arquivo de template do certificado não encontrado no servidor.", 404

    bg_width = float(page.mediabox.width)
    bg_height = float(page.mediabox.height)
    center_x = bg_width / 2.0

    # =========================================================================
    # 3. RENDERIZAÇÃO DA TIPOGRAFIA ULTRA-DETALHADA (OVERLAY)
    # =========================================================================
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=(bg_width, bg_height))
    
    # --- CONFIGURAÇÃO DO NOME DO ALUNO (IM PONENTE) ---
    can.setFont("Helvetica-Bold", 40)                     # Fonte aumentada para destaque absoluto
    can.setFillColorRGB(0, 0, 0)                          # Cor Preta
    
    # Subi levemente o Y do nome (48% da altura) para dar espaço ao texto maior abaixo
    pos_y_nome = bg_height * 0.55 
    can.drawCentredString(center_x, pos_y_nome, member_name.upper()) 
    
    # --- CONFIGURAÇÃO DO TEXTO JURÍDICO/ACADÊMICO ---
    can.setFont("Helvetica", 16)                          # Fonte aumentada para preencher o centro
    can.setFillColorRGB(0.2, 0.2, 0.2)                    # Cinza claro de alto contraste
    
    # Texto encorpado contendo todas as variáveis que você solicitou
    texto_linha1 = f"Concluiu com êxito os desafios propostos pelo evento"
    texto_linha2 = f"{event_title}, realizada na instituição {inst_name},"
    texto_linha3 = f"{date_range_str}, cumprindo integralmente uma carga horária"
    texto_linha4 = f"de 12 horas de desafios práticos de Programação e Cibersegurança."

    # Renderização linha por linha com espaçamento (leading) de 25 pontos entre elas
    pos_y_texto_inicial = bg_height * 0.50
    can.drawCentredString(center_x, pos_y_texto_inicial, texto_linha1)
    can.drawCentredString(center_x, pos_y_texto_inicial - 25, texto_linha2)
    can.drawCentredString(center_x, pos_y_texto_inicial - 50, texto_linha3)
    can.drawCentredString(center_x, pos_y_texto_inicial - 75, texto_linha4)
    
    can.save()
    packet.seek(0)

    # =========================================================================
    # 4. COMPILAÇÃO DO ARQUIVO BINÁRIO E DISPARO DE DOWNLOAD
    # =========================================================================
    try:
        new_pdf = PdfReader(packet)
        output = PdfWriter()
        
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        
        response_stream = io.BytesIO()
        output.write(response_stream)
        response_stream.seek(0)
        
        filename = f"Certificado_AsyncX_{member_name.replace(' ', '_')}.pdf"
        
        return send_file(
            response_stream,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return f"Erro interno ao injetar metadados no certificado: {str(e)}", 500
    

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    # Roda nativamente local na porta padrão 5000
    app.run(host='127.0.0.1', port=5000, debug=True)