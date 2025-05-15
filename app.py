from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
import fitz  
from langchain.schema import Document
from werkzeug.utils import secure_filename
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import openai
from openai import OpenAI 
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

print("Clé API chargée:", api_key)

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'csv'}  


app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER  
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.secret_key = 'e1fa20f7aae8713701fd7c18fbc72841eb3347742a57ac4d5e8de28bc17293ad'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modèle utilisateur
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

with app.app_context():
    db.create_all()

# Initialisation de l'embedding et du vectorstore
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.load_local("vectorstore_index", embeddings, allow_dangerous_deserialization=True)

def search_documents(query):
    docs = vectorstore.similarity_search(query, k=3)
    return [doc.page_content for doc in docs]

# Route accueil
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')  # Page d'accueil
limiter = Limiter(get_remote_address, app=app)

# Route login
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per 1 minute")  # Limite à 5 tentatives par minute
def login_post():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Si un champ est vide, on refuse immédiatement
        if not username or not password:
            flash('Veuillez remplir tous les champs.', 'danger')
            return render_template("login.html") 

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants invalides ou utilisateur non trouvé. Essayez à nouveau.', 'danger')
            return render_template("login.html")

    return render_template("login.html")

# Route register
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Vérifie si les champs sont remplis
        if not username or not password:
            flash('Veuillez remplir tous les champs pour vous inscrire.', 'danger')
            return render_template("login.html")  # RESTER sur login.html !

        # Vérifie si l'utilisateur existe déjà
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Nom d\'utilisateur déjà pris!', 'danger')
            return render_template("login.html")  # RESTER sur login.html aussi
        else:
            new_user = User(username=username)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            flash('Inscription réussie! Veuillez vous connecter.', 'success')
            return render_template("login.html")  # Inscription réussie -> redirige vers page accueil
    else:
        return render_template("login.html")  # Si GET, afficher login.html aussi

# Vérifier si le fichier est un PDF
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Fonction pour extraire le texte d'un PDF
def extract_pdf_text(pdf_path):
    document = fitz.open(pdf_path)
    text = ""
    for page in document:
        text += page.get_text()  # Récupérer le texte de chaque page
    return text

@app.route("/dashboard")
def dashboard():
    if "username" in session:
        return render_template("dashboard.html", username=session['username'])
    return redirect(url_for('home'))

# Route logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

# Route pour gérer le téléchargement du PDF
from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document



@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf_file' not in request.files:
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('dashboard'))
    
    pdf_file = request.files['pdf_file']
    
    if pdf_file.filename == '':
        flash('Aucun fichier sélectionné', 'danger')
        return redirect(url_for('dashboard'))
    
    if pdf_file and allowed_file(pdf_file.filename):
        # Sécuriser le nom du fichier et l'enregistrer
        filename = secure_filename(pdf_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pdf_file.save(filepath)

        # Extraire le texte du PDF avec PyMuPDF
        texte_pdf = extract_pdf_text(filepath)


        # 1. Splitter le texte en chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = splitter.split_text(texte_pdf)

        # 2. Transformer les chunks en objets Document
        docs = [Document(page_content=chunk, metadata={"source": filename}) for chunk in chunks]

        # 3. Ajouter ces documents au vectorstore existant
        vectorstore.add_documents(docs)

        # 4. Sauvegarder l’index mis à jour
        vectorstore.save_local("vectorstore_index")

        # ---------------------------------------

        flash('Fichier téléchargé, traité et indexé avec succès!', 'success')

        # Préserver l'historique des messages dans la session (si existant)
        if 'conversation_history' not in session:
            session['conversation_history'] = []

        # Passer le texte extrait du PDF à la page dashboard et conserver l'historique
        return render_template('dashboard.html', texte_pdf=texte_pdf, conversation_history=session['conversation_history'])

    flash('Le fichier doit être un PDF.', 'danger')
    return redirect(url_for('dashboard'))

client = OpenAI(api_key=api_key)

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')

    try:
        if 'conversation_history' not in session:
            session['conversation_history'] = []

        session['conversation_history'].append({'role': 'user', 'content': user_message})

        # Simuler la recherche vectorielle (à remplacer par ton vrai code)
        docs = vectorstore.similarity_search(user_message, k=2)
        context = "\n".join([doc.page_content for doc in docs]) if docs else ""

        prompt = f"""
Tu es un assistant intelligent.

Voici des informations extraites de documents internes (si disponibles) :
{context if context else '[Aucune information pertinente trouvée]'}

Réponds à la question suivante. Si les documents contiennent la réponse, base-toi dessus. Sinon, utilise tes connaissances générales :
Question : {user_message}
"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )

        answer = response.choices[0].message.content.strip()
        session['conversation_history'].append({'role': 'assistant', 'content': answer})

        return jsonify({'response': answer})

    except Exception as e:
        return jsonify({'response': f"Erreur serveur : {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)