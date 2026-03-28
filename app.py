import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, session, flash
from datetime import datetime

# (Ano, mês, dia, hora, minuto, segundo)
EVENT_END = datetime(2026, 3, 14, 12, 0, 0)

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

@app.route('/')
def index():
    if 'team_id' in session: return redirect('/dashboard')
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form['name']
    password = request.form['password']
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM teams WHERE name = %s AND password = %s', (name, password))
    team = cur.fetchone()
    cur.close()
    conn.close()
    
    if team:
        session['team_id'] = team['id']
        session['team_name'] = team['name']
        return redirect('/dashboard')
    return "Credenciais Incorretas", 401

@app.route('/dashboard')
def dashboard():
    if 'team_id' not in session: return redirect('/')
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM challenges')
    challenges = cur.fetchall()
    
    cur.execute('SELECT challenge_id FROM solves WHERE team_id = %s', (session['team_id'],))
    solved_ids = [row['challenge_id'] for row in cur.fetchall()]
    
    cur.execute('SELECT challenge_id FROM hint_purchases WHERE team_id = %s', (session['team_id'],))
    purchased_ids = [row['challenge_id'] for row in cur.fetchall()]
    
    cur.execute('''
    SELECT name, score 
    FROM teams 
    ORDER BY 
        score DESC,               
        last_solve ASC NULLS LAST, 
        name ASC                  
    ''')
    ranking = cur.fetchall()
    
    cur.close()
    conn.close()
    
    vms = [{"name": "Máquina Ciberdetetive (.OVA)", "url": "https://drive.google.com/..."}]
    
    return render_template('dashboard.html', 
                           challenges=challenges, 
                           solved_ids=solved_ids, 
                           purchased_ids=purchased_ids,
                           ranking=ranking, 
                           vms=vms,
                           end_time=EVENT_END.isoformat())

@app.route('/hint/<int:id>')
def get_hint(id):
    if 'team_id' not in session: return "Acesso negado", 403
    if datetime.now() > EVENT_END:
        return {"hint": "O evento terminou! Não é mais possível solicitar dicas.", "error": True}

    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT 1 FROM hint_purchases WHERE team_id = %s AND challenge_id = %s', 
                (session['team_id'], id))
    already_purchased = cur.fetchone()
    
    if already_purchased:
        cur.execute('SELECT hint FROM challenges WHERE id = %s', (id,))
        hint = cur.fetchone()
        cur.close()
        conn.close()
        return {"hint": hint['hint']}

    cur.execute('SELECT 1 FROM solves WHERE team_id = %s AND challenge_id = %s', 
                (session['team_id'], id))
    already_solved = cur.fetchone()
    
    if already_solved:
        cur.close()
        conn.close()
        return {"hint": "Desafio já concluído!", "error": True}
    
    cur.execute('UPDATE teams SET score = score - 25 WHERE id = %s', (session['team_id'],))
    cur.execute('INSERT INTO hint_purchases (team_id, challenge_id) VALUES (%s, %s)', 
                (session['team_id'], id))
    conn.commit()
    
    cur.execute('SELECT hint FROM challenges WHERE id = %s', (id,))
    hint = cur.fetchone()
    cur.close()
    conn.close()
    return {"hint": hint['hint']}

@app.route('/submit', methods=['POST'])
def submit():
    if datetime.now() > EVENT_END:
        flash("O evento terminou! Submissões encerradas.", "danger")
        return redirect('/dashboard')

    challenge_id = request.form.get('challenge_id')
    flag = request.form['flag'].strip()
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM challenges WHERE id = %s AND flag = %s', (challenge_id, flag))
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
            flash("Flag correta! Pontos adicionados.", "success")
    else:
        flash("Flag incorreta! Tente novamente em 3 segundos.", "danger")
        
    cur.close()
    conn.close()
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/downloads')
def downloads():
    if 'team_id' not in session: return redirect('/')
    
    maquinas = [
        {"nome": "00. INTRODUÇÃO", "img": "m0.png", "link": "https://drive.google.com/file/d/1jtQxB2gZjab9Rz-qBUbakgvfvRd469aw/view?usp=sharing"},
        {"nome": "01. GENESIS", "img": "m1.png", "link": "https://drive.google.com/file/d/1M7BlJNNsjYLndwG_J5AMpezzU0MPMFS-/view?usp=sharing"},
        {"nome": "02. DATALEAKY", "img": "m2.png", "link": "https://drive.google.com/file/d/1MoNQFvU6Qyg60NGWsRqoa7tiqegDlpSz/view?usp=sharing"},
        {"nome": "03. AUTOMATOR", "img": "m3.png", "link": "https://drive.google.com/file/d/1da-p3aUWp8DI1kvlSTcT-eUnfj6x5X7r/view?usp=sharing"},
        {"nome": "04. DEPENDENCY", "img": "m4.png", "link": "https://drive.google.com/file/d/1urPjKbCQL3LjY6LTI6VGH5oVcO3kqyHd/view?usp=sharing"},
        {"nome": "05. MEMORYLANE", "img": "m5.png", "link": "https://drive.google.com/file/d/1cM-TrEBjzERaoKp1DrqvMmN200XjGq-K/view?usp=sharing"},
        {"nome": "06. NIGHTMARE", "img": "m6.png", "link": "https://drive.google.com/file/d/1NX4s3y6E4dO_DQLOojhTdVrccTU8sOUs/view?usp=sharing"},
        {"nome": "07. OVERSEER", "img": "m7.png", "link": "https://drive.google.com/file/d/1daMoHSo90F1SSwNyZ62FJTJe3EpNlRn7/view?usp=sharing"},
        {"nome": "08. LEAKYREPO", "img": "m8.png", "link": "https://drive.google.com/file/d/1pwaDvFhes4BMlscflzDrv49pp3mnPsRu/view?usp=sharing"},
        {"nome": "09. SHAREDFILE", "img": "m9.png", "link": "https://drive.google.com/file/d/1VPqhevy5pNmmSk3Q2uRnxPAbr-QWv02r/view?usp=sharing"},
        {"nome": "10. GATEKEEPER", "img": "m10.png", "link": "https://drive.google.com/file/d/1Mt9vk-DESA-541tqgPiRkcF2p6rkBrIr/view?usp=sharing"},
        {"nome": "11. REQUEST", "img": "m11.png", "link": "https://drive.google.com/file/d/1hRinaOeLORk5jdqVqeY7005iVPfxalsq/view?usp=sharing"},
    ]
    
    return render_template('downloads.html', maquinas=maquinas)

@app.route('/leaderboard')
def leaderboard_public():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    SELECT name, score 
    FROM teams 
    ORDER BY 
        score DESC,               
        last_solve ASC NULLS LAST, 
        name ASC                  
    ''')
    ranking = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('leaderboard_public.html', ranking=ranking, end_time=EVENT_END.isoformat())

@app.route('/api/score')
def api_score():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    SELECT name, score 
    FROM teams 
    ORDER BY 
        score DESC,               
        last_solve ASC NULLS LAST, 
        name ASC                  
    ''')
    ranking = cur.fetchall()
    cur.close()
    conn.close()
    return {"ranking": [dict(row) for row in ranking]}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)