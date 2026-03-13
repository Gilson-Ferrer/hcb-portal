import os
import time
from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
from datetime import datetime

# Defina EXATAMENTE quando o evento termina (Ano, Mês, Dia, Hora, Minuto)
EVENT_END = datetime(2026, 2, 15, 13, 50, 0)

app = Flask(__name__)
app.secret_key = 'chave_mestra_asyncx'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'hcb.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'team_id' in session: return redirect('/dashboard')
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    name = request.form['name']
    password = request.form['password']
    db = get_db()
    team = db.execute('SELECT * FROM teams WHERE name = ? AND password = ?', (name, password)).fetchone()
    if team:
        session['team_id'] = team['id']
        session['team_name'] = team['name']
        return redirect('/dashboard')
    return "Credenciais Incorretas", 401

@app.route('/dashboard')
def dashboard():
    if 'team_id' not in session: return redirect('/')
    db = get_db()
    
    challenges = db.execute('SELECT * FROM challenges').fetchall()
    solved_rows = db.execute('SELECT challenge_id FROM solves WHERE team_id = ?', 
                            (session['team_id'],)).fetchall()
    solved_ids = [row['challenge_id'] for row in solved_rows]
    
    purchased_rows = db.execute('SELECT challenge_id FROM hint_purchases WHERE team_id = ?', 
                               (session['team_id'],)).fetchall()
    purchased_ids = [row['challenge_id'] for row in purchased_rows]
    
    ranking = db.execute('''
        SELECT name, score 
        FROM teams 
        ORDER BY score DESC, last_solve ASC
    ''').fetchall()
    
    vms = [{"name": "Máquina Ciberdetetive (.OVA)", "url": "https://drive.google.com/..."}]
    
    return render_template('dashboard.html', 
                           challenges=challenges, 
                           solved_ids=solved_ids, 
                           purchased_ids=purchased_ids, # Passa para o HTML
                           ranking=ranking, 
                           vms=vms,
                           end_time=EVENT_END.isoformat()) # Garante o relógio


@app.route('/hint/<int:id>')
def get_hint(id):
    if 'team_id' not in session: return "Acesso negado", 403
    if datetime.now() > EVENT_END:
        return {"hint": "O evento terminou! Não é mais possível solicitar dicas.", "error": True}

    db = get_db()
    
    already_purchased = db.execute('SELECT 1 FROM hint_purchases WHERE team_id = ? AND challenge_id = ?', 
                                  (session['team_id'], id)).fetchone()
    
    if already_purchased:
        hint = db.execute('SELECT hint FROM challenges WHERE id = ?', (id,)).fetchone()
        return {"hint": hint['hint']}

    already_solved = db.execute('SELECT 1 FROM solves WHERE team_id = ? AND challenge_id = ?', 
                               (session['team_id'], id)).fetchone()
    if already_solved:
        return {"hint": "Desafio já concluído!", "error": True}
    
    db.execute('UPDATE teams SET score = score - 25 WHERE id = ?', (session['team_id'],))
    db.execute('INSERT INTO hint_purchases (team_id, challenge_id) VALUES (?, ?)', (session['team_id'], id))
    db.commit()
    
    hint = db.execute('SELECT hint FROM challenges WHERE id = ?', (id,)).fetchone()
    return {"hint": hint['hint']}

@app.route('/submit', methods=['POST'])
def submit():
    if datetime.now() > EVENT_END:
        flash("O evento terminou! Submissões encerradas.", "danger")
        return redirect('/dashboard')

    challenge_id = request.form.get('challenge_id')
    flag = request.form['flag'].strip()
    db = get_db()
    
    challenge = db.execute('SELECT * FROM challenges WHERE id = ? AND flag = ?', 
                          (challenge_id, flag)).fetchone()
    
    if challenge:
        already = db.execute('SELECT * FROM solves WHERE team_id = ? AND challenge_id = ?',
                            (session['team_id'], challenge['id'])).fetchone()
        if not already:
            db.execute('INSERT INTO solves (team_id, challenge_id) VALUES (?, ?)', 
                      (session['team_id'], challenge['id']))
            
            agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute('UPDATE teams SET score = score + ?, last_solve = ? WHERE id = ?', 
                      (challenge['points'], agora, session['team_id']))
            
            db.commit()
            flash("Flag correta! Pontos adicionados.", "success")
    else:
        flash("Flag incorreta! Tente novamente em 3 segundos.", "danger")
        time.sleep(3)        
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/downloads')
def downloads():
    if 'team_id' not in session: return redirect('/')
    
    # Lista com as 12 máquinas (Grade 3x4)
    maquinas = [
        {"nome": "01. GENESIS", "img": "m1.png", "link": "https://drive.google.com/file/d/1OrzgoWxRZ_LCZinrhRX9bmy19kbWGeNu/view?usp=sharing"},
        {"nome": "02. DATALEAKY", "img": "m2.png", "link": "https://drive.google.com/file/d/1d5mg4RcFEymEgWGs3mo8jQnTuiCTd2qg/view?usp=sharing"},
        {"nome": "03. Forensic Analyst", "img": "m3.png", "link": "https://drive.google.com/link3"},
        {"nome": "04. SQL Injector Pro", "img": "m4.png", "link": "https://drive.google.com/link4"},
        {"nome": "05. Cryptography Basics", "img": "m5.png", "link": "https://drive.google.com/link5"},
        {"nome": "06. Network Scanner", "img": "m6.png", "link": "https://drive.google.com/link6"},
        {"nome": "07. Linux Hardening", "img": "m7.png", "link": "https://drive.google.com/link7"},
        {"nome": "08. Brute Force Defense", "img": "m8.png", "link": "https://drive.google.com/link8"},
        {"nome": "09. Malware Analysis", "img": "m9.png", "link": "https://drive.google.com/link9"},
        {"nome": "10. Cloud Security", "img": "m10.png", "link": "https://drive.google.com/link10"},
        {"nome": "11. Buffer Overflow", "img": "m11.png", "link": "https://drive.google.com/link11"},
        {"nome": "12. Final Boss Challenge", "img": "m12.png", "link": "https://drive.google.com/link12"},
    ]
    
    return render_template('downloads.html', maquinas=maquinas)


@app.route('/leaderboard')
def leaderboard_public():
    db = get_db()
    # Busca o ranking com o critério de desempate por tempo (last_solve)
    ranking = db.execute('''
        SELECT name, score 
        FROM teams 
        ORDER BY score DESC, last_solve ASC
    ''').fetchall()

    return render_template('leaderboard_public.html', ranking=ranking, end_time=EVENT_END.isoformat())

@app.route('/api/score')
def api_score():
    db = get_db()
    ranking = db.execute('SELECT name, score FROM teams ORDER BY score DESC, last_solve ASC').fetchall()
    return {"ranking": [dict(row) for row in ranking]}


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)