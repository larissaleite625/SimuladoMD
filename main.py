# main.py
import os, re, json, csv
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, Frame, Label, Button, Checkbutton, StringVar, scrolledtext, Canvas, Scrollbar

from dotenv import load_dotenv
from openai import OpenAI

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# -------------------------- CONFIG GLOBAL --------------------------
load_dotenv()

try:
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
except Exception as e:
    print(f"Erro ao inicializar o cliente da API: {e}")
    client = None

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_FOLDER_NAME = "logs"
RESULTS_FILENAME = "results.csv"

# -------------------------- FUNÇÕES DE I/O --------------------------
def is_chapter_dir(name: str) -> bool:
    """Capítulo: diretório cujo nome começa com dígito."""
    return bool(re.match(r"^\d", name))

def _looks_like_simulado(sim_path: str) -> bool:
    """Heurística: tem results.csv OU tem capítulos diretos OU em ./conteudo."""
    if not os.path.isdir(sim_path):
        return False
    has_csv = os.path.exists(os.path.join(sim_path, RESULTS_FILENAME))
    try:
        immediate = [d for d in os.listdir(sim_path) if os.path.isdir(os.path.join(sim_path, d))]
    except FileNotFoundError:
        immediate = []

    has_chapter_direct = any(d != LOGS_FOLDER_NAME and is_chapter_dir(d) for d in immediate)

    conteudo = os.path.join(sim_path, "conteudo")
    has_chapter_in_conteudo = False
    if os.path.isdir(conteudo):
        try:
            has_chapter_in_conteudo = any(
                is_chapter_dir(d) for d in os.listdir(conteudo)
                if os.path.isdir(os.path.join(conteudo, d))
            )
        except FileNotFoundError:
            pass
    return has_csv or has_chapter_direct or has_chapter_in_conteudo


def list_simulados():
    """
    Lista todos os simulados válidos:
    - Diretórios na raiz que não sejam ocultos, logs, nenv, etc.
    - Diretórios em conteudo/ que não sejam logs, etc.
    - Mostra diretórios mesmo se estiverem vazios, para permitir novos simulados.
    """
    sims = set()
    excl = {"__pycache__", "venv", "env", "nenv", LOGS_FOLDER_NAME, "conteudo", "logs"}
    # raiz
    for d in os.listdir(ROOT_DIR):
        full = os.path.join(ROOT_DIR, d)
        if not os.path.isdir(full):
            continue
        if d.startswith(".") or d in excl:
            continue
        sims.add(d)
    # conteudo/
    conteudo_dir = os.path.join(ROOT_DIR, "conteudo")
    if os.path.isdir(conteudo_dir):
        for d in os.listdir(conteudo_dir):
            full = os.path.join(conteudo_dir, d)
            if not os.path.isdir(full) or d in excl:
                continue
            sims.add(d)
    return sorted(sims, key=str.lower)

def resolve_simulado_root(simulado_name: str) -> str:
    """Raiz do simulado (novo: ./simulado; antigo: ./conteudo/simulado)."""
    cand1 = os.path.join(ROOT_DIR, simulado_name)                 # novo
    cand2 = os.path.join(ROOT_DIR, "conteudo", simulado_name)     # antigo
    if os.path.isdir(cand1):
        return cand1
    if os.path.isdir(cand2):
        return cand2
    return cand1  # fallback

def resolve_simulado_root(simulado_name: str) -> str:
    """Raiz do simulado (novo: ./simulado; antigo: ./conteudo/simulado)."""
    cand1 = os.path.join(ROOT_DIR, simulado_name)                 # novo
    cand2 = os.path.join(ROOT_DIR, "conteudo", simulado_name)     # antigo
    if os.path.isdir(cand1):
        return cand1
    if os.path.isdir(cand2):
        return cand2
    return cand1  # fallback

def resolve_chapter_base(simulado_name: str) -> str:
    """
    Base onde ficam os capítulos. Prioridade:
    1. ./conteudo/<simulado>/ (layout antigo)
    2. ./<simulado>/ (layout novo)
    """
    # layout antigo
    old_base = os.path.join(ROOT_DIR, "conteudo", simulado_name)
    if os.path.isdir(old_base):
        return old_base
    # layout novo
    new_base = os.path.join(ROOT_DIR, simulado_name)
    if os.path.isdir(new_base):
        return new_base
    return new_base  # fallback

def ensure_simulado_structure_for(simulado_name: str):
    """Cria logs/ e results.csv no lugar correto do simulado."""
    sim_root = resolve_simulado_root(simulado_name)
    os.makedirs(os.path.join(sim_root, LOGS_FOLDER_NAME), exist_ok=True)
    results_csv = os.path.join(sim_root, RESULTS_FILENAME)
    if not os.path.exists(results_csv):
        with open(results_csv, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["arquivo_md", "data", "hora", "acertos", "erros", "total_perguntas"])



def ensure_simulado_structure(simulado_dir: str):
    """Garante logs/ e results.csv dentro do simulado selecionado."""
    os.makedirs(os.path.join(simulado_dir, LOGS_FOLDER_NAME), exist_ok=True)
    results_csv = os.path.join(simulado_dir, RESULTS_FILENAME)
    if not os.path.exists(results_csv):
        with open(results_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["arquivo_md", "data", "hora", "acertos", "erros", "total_perguntas"])

def get_chapters(simulado_name: str):
    """
    Retorna lista de capítulos (diretórios cujo nome começa com dígito) do simulado.
    Considera tanto diretórios na raiz do simulado quanto em simulado/conteudo/.
    """
    base = resolve_chapter_base(simulado_name)
    try:
        dirs = [
            d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))
            and d != LOGS_FOLDER_NAME
            and is_chapter_dir(d)
        ]
        def keyfn(x):
            m = re.match(r"^(\d+)", x)
            return (int(m.group(1)) if m else float("inf"), x.lower())
        return sorted(dirs, key=keyfn)
    except Exception:
        return []



def read_file(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None

def get_md_content(simulado_name: str, chapter_name: str, file_name: str):
    return read_file(os.path.join(ROOT_DIR, simulado_name, chapter_name, file_name))

def get_md_content(simulado_name: str, chapter_name: str, file_name: str):
    file_path = os.path.join(resolve_chapter_base(simulado_name), chapter_name, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    
def get_md_content(simulado_name: str, chapter_name: str, file_name: str):
    """Use sempre a base resolvida (não o ROOT direto)."""
    file_path = os.path.join(resolve_chapter_base(simulado_name), chapter_name, file_name)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None
    
def get_all_md_content_from_chapter(simulado_name: str, chapter_name: str):
    all_content = []
    for f in get_md_files(simulado_name, chapter_name):
        c = get_md_content(simulado_name, chapter_name, f)
        if c:
            all_content.append(c)
    return "\n\n---\n\n".join(all_content)

def get_all_md_content_from_chapter(simulado_name: str, chapter_name: str):
    all_content = []
    for f in get_md_files(simulado_name, chapter_name):
        c = get_md_content(simulado_name, chapter_name, f)
        if c:
            all_content.append(c)
    return "\n\n---\n\n".join(all_content)

def get_md_files(simulado_name: str, chapter_name: str):
    """Retorna lista de arquivos .md no capítulo (ordenada)."""
    base = resolve_chapter_base(simulado_name)
    chapter_path = os.path.join(base, chapter_name)
    try:
        files = [
            f for f in os.listdir(chapter_path)
            if os.path.isfile(os.path.join(chapter_path, f)) and f.lower().endswith('.md')
        ]
        return sorted(files, key=lambda x: x.lower())
    except FileNotFoundError:
        return []

# -------------------------- LLM --------------------------
def generate_questions_from_api(content: str, num_questions: int = 10):
    if not client:
        messagebox.showerror("Erro de API", "O cliente da API não foi inicializado.")
        return None

    prompt = f"""
Você deve responder SOMENTE com um array JSON (sem texto fora do array). O array deve ter exatamente {num_questions} objetos.
Cada objeto terá as chaves:
- \"question\": string
- \"options\": array de 4 strings, na ordem A, B, C, D
- \"answer\": array de letras corretas, cada uma em [\"A\",\"B\",\"C\",\"D\"] (ex.: [\"C\"] ou [\"A\",\"D\"])
- \"explanation_cue\": string curta do texto original

NÃO escreva nada antes/depois do array. NÃO use aspas simples.
--- CONTEÚDO PARA ANÁLISE ---
{content}
"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um gerador de testes. Saída EXCLUSIVAMENTE em JSON válido (array)."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=2048,
        )
        raw = (response.choices[0].message.content or "").strip()

        # extrai o primeiro array
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if not m:
            raise ValueError("Não foi possível localizar um array JSON na resposta da API.")
        data = json.loads(m.group(0))

        # normalização mínima
        letter_set = {"A", "B", "C", "D"}
        norm = []
        for i, q in enumerate(data):
            for k in ("question", "options", "answer", "explanation_cue"):
                if k not in q:
                    raise ValueError(f"Item {i+1}: chave ausente '{k}'.")
            if not isinstance(q["options"], list) or len(q["options"]) != 4:
                raise ValueError(f"Item {i+1}: 'options' deve ter 4 itens.")
            ans = q["answer"]
            if isinstance(ans, str):
                ans = [ans]
            if not isinstance(ans, list) or not all(isinstance(x, str) for x in ans):
                raise ValueError(f"Item {i+1}: 'answer' deve ser array de letras.")
            ans = [x.strip().upper() for x in ans]
            if not all(x in letter_set for x in ans):
                converted = []
                for x in ans:
                    if x.isdigit() and int(x) in range(4):
                        converted.append("ABCD"[int(x)])
                    else:
                        try:
                            idx = q["options"].index(x)
                            converted.append("ABCD"[idx])
                        except ValueError:
                            raise ValueError(f"Item {i+1}: valor de answer inválido: {x!r}")
                ans = converted
            q["answer"] = sorted(set(ans))
            norm.append(q)
        return norm
    except Exception as e:
        messagebox.showerror("Erro de API", f"Ocorreu um erro ao processar a resposta da API: {e}")
        return None

def find_explanation_in_text(full_text, cue):
    for p in full_text.split("\n\n"):
        if cue in p:
            return p.strip()
    return "Contexto não encontrado no texto original."

# -------------------------- GUI --------------------------
class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SimuladoMD - Gerador de Testes")
        self.root.geometry("900x700")
        self.current_frame = None

        # Tema escuro
        self.is_dark_theme = False
        self.colors = {
            "light": {
                "bg": "#f0f0f0",
                "fg": "#222",
                "button_bg": "#cce5ff",
                "button_fg": "#222",
                "accent": "#d0e0ff",
                "correct_bg": "#d4edda",
                "correct_fg": "#155724",
                "wrong_bg": "#f8d7da",
                "wrong_fg": "#721c24",
                "explanation_bg": "#e0e0e0",
                "stats_bg": "#e9ecef",
            },
            "dark": {
                "bg": "#222",
                "fg": "#f0f0f0",
                "button_bg": "#444",
                "button_fg": "#f0f0f0",
                "accent": "#333",
                "correct_bg": "#2e7d32",
                "correct_fg": "#c8e6c9",
                "wrong_bg": "#c62828",
                "wrong_fg": "#ffcdd2",
                "explanation_bg": "#333",
                "stats_bg": "#333",
            }
        }

        # estado atual
        self.current_simulado = None
        self.md_filename = None
        self.md_content = None
        self.questions = []
        self.user_answers = []

        self.start_initial_screen()

    def get_color(self, key):
        theme = "dark" if self.is_dark_theme else "light"
        return self.colors[theme][key]

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.root.configure(bg=self.get_color("bg"))
        self.start_initial_screen()

    # util
    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root, bg=self.get_color("bg"))
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

    # -------- PÁGINA INICIAL --------
    def start_initial_screen(self):
        self.clear_frame()
        Label(self.current_frame, text="Bem-vindo ao SimuladoMD!", font=("Helvetica", 24, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(10, 20))
        Label(self.current_frame, text="Escolha uma opção:", font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 20), anchor="w")

        Button(self.current_frame, text="🚀 Iniciar Novo Simulado", font=("Helvetica", 12, "bold"),
               command=lambda: self.show_simulado_selection(mode="quiz"),
               width=40, height=2, bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=10)

        Button(self.current_frame, text="📊 Ver Meu Progresso", font=("Helvetica", 12, "bold"),
               command=lambda: self.show_simulado_selection(mode="dashboard"),
               width=40, height=2, bg=self.get_color("accent"), fg=self.get_color("button_fg")).pack(pady=10)

        Button(self.current_frame, text=("🌙 Tema Escuro" if not self.is_dark_theme else "☀️ Tema Claro"),
               font=("Helvetica", 12), command=self.toggle_theme,
               bg=self.get_color("button_bg"), fg=self.get_color("button_fg"), width=20).pack(pady=(30, 0))

    # -------- SELECIONAR SIMULADO --------
    def show_simulado_selection(self, mode: str):
        self.clear_frame()
        Label(self.current_frame, text="Escolha o simulado:", font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 20), anchor="w")

        sims = list_simulados()
        if not sims:
            Label(self.current_frame, text="Nenhum simulado encontrado. Crie uma pasta (ex.: dp900) com capítulos dentro.", font=("Helvetica", 12),
                  fg="red", bg=self.get_color("bg")).pack()
        else:
            for s in sims:
                if mode == "quiz":
                    cb = lambda name=s: self.show_chapter_selection_screen(name)
                else:
                    cb = lambda name=s: self.show_dashboard(name)
                Button(self.current_frame, text=s, font=("Helvetica", 12), command=cb, width=40, height=2, bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=5)

        Button(self.current_frame, text="← Voltar ao Início", command=self.start_initial_screen, font=("Helvetica", 12), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=(20, 0))

    # -------- SELECIONAR CAPÍTULO/ARQUIVO --------
    def show_chapter_selection_screen(self, simulado_name):
        self.current_simulado = simulado_name
        simulado_dir = os.path.join(ROOT_DIR, simulado_name)
        ensure_simulado_structure(simulado_dir)

        self.clear_frame()
        Label(self.current_frame, text=f"Simulado: {simulado_name}", font=("Helvetica", 24, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(10, 20))
        Label(self.current_frame, text="1. Escolha um capítulo:", font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 20), anchor="w")

        chapters = get_chapters(simulado_name)
        if not chapters:
            Label(self.current_frame, text="Nenhum capítulo encontrado.", font=("Helvetica", 12), fg="red", bg=self.get_color("bg")).pack()
        else:
            for chapter in chapters:
                Button(self.current_frame, text=f"Capítulo {chapter}", font=("Helvetica", 12),
                       command=lambda c=chapter: self.show_file_selection_screen(simulado_name, c), width=40, height=2, bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=5)

        Button(self.current_frame, text="← Voltar (Simulados)", command=lambda: self.show_simulado_selection("quiz"), font=("Helvetica", 12), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=(20, 0))

    def show_file_selection_screen(self, simulado_name, chapter_name):
        self.clear_frame()
        Label(self.current_frame, text=f"{simulado_name} • Capítulo {chapter_name}", font=("Helvetica", 24, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(10, 20))
        Label(self.current_frame, text="2. Escolha uma opção:", font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 10), anchor="w")

        # NOVO: campo para escolher número de perguntas
        Label(self.current_frame, text="Quantas perguntas deseja gerar? (1-50)", font=("Helvetica", 12), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 5), anchor="w")
        self.num_questions_var = tk.IntVar(value=10)
        num_entry = tk.Entry(self.current_frame, textvariable=self.num_questions_var, width=5, font=("Helvetica", 12), bg=self.get_color("bg"), fg=self.get_color("fg"))
        num_entry.pack(pady=(0, 10), anchor="w")

        Button(self.current_frame, text="▶ Gerar teste do capítulo inteiro", font=("Helvetica", 12, "bold"),
               command=lambda: self.start_quiz(simulado_name, chapter_name, None, self.num_questions_var.get()), bg=self.get_color("accent"), fg=self.get_color("button_fg")).pack(pady=(5, 15), fill="x", ipady=5)

        Label(self.current_frame, text="Ou escolha um arquivo específico:", font=("Helvetica", 12, "italic"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 10), anchor="w")

        md_files = get_md_files(simulado_name, chapter_name)
        if not md_files:
            Label(self.current_frame, text="Nenhum arquivo .md encontrado.", font=("Helvetica", 12), fg="red", bg=self.get_color("bg")).pack()
        else:
            for md_file in md_files:
                Button(self.current_frame, text=md_file, font=("Helvetica", 12),
                       command=lambda f=md_file: self.start_quiz(simulado_name, chapter_name, f, self.num_questions_var.get()),
                       wraplength=500, justify="left", bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=5, fill="x")

        Button(self.current_frame, text="← Voltar (Capítulos)", command=lambda: self.show_chapter_selection_screen(simulado_name), font=("Helvetica", 12), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=(20, 0), anchor="s")

    # -------- QUIZ --------
    def start_quiz(self, simulado_name, chapter_name, file_name=None, num_questions=10):
        self.clear_frame()
        # Temporizador e bolinha girando
        loading_frame = Frame(self.current_frame, bg=self.get_color("bg"))
        loading_frame.pack(pady=50)
        Label(loading_frame, text="Gerando perguntas...\nAguarde um momento.", font=("Helvetica", 16), bg=self.get_color("bg"), fg=self.get_color("fg")).pack()
        timer_label = Label(loading_frame, text="00:00", font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg"))
        timer_label.pack(pady=10)
        canvas = Canvas(loading_frame, width=40, height=40, bg=self.get_color("bg"), highlightthickness=0)
        canvas.pack()
        ball = canvas.create_oval(10, 10, 30, 30, fill="#007bff" if not self.is_dark_theme else "#ffc107")

        self.root.update()
        import time
        start_time = time.time()
        angle = 0
        running = True
        def animate():
            nonlocal angle
            if not running:
                return
            angle = (angle + 15) % 360
            x = 10 + 10 * (1 + 0.7 * (math.cos(math.radians(angle))))
            y = 10 + 10 * (1 + 0.7 * (math.sin(math.radians(angle))))
            canvas.coords(ball, x, y, x+20, y+20)
            elapsed = int(time.time() - start_time)
            timer_label.config(text=f"{elapsed//60:02d}:{elapsed%60:02d}")
            self.root.after(60, animate)
        import math
        animate()
        self.root.update()

        self.md_filename = (f"{simulado_name} • Capítulo {chapter_name} (Completo)" if not file_name else file_name)
        self.md_content = (
            get_all_md_content_from_chapter(simulado_name, chapter_name)
            if not file_name else
            get_md_content(simulado_name, chapter_name, file_name)
        )
        self.root.update()
        running = False  # para parar animação
        if not self.md_content:
            messagebox.showerror("Erro", f"Não foi possível encontrar conteúdo para '{self.md_filename}'.")
            self.show_file_selection_screen(simulado_name, chapter_name)
            return

        self.questions = generate_questions_from_api(self.md_content, num_questions)
        self.root.update()
        running = False
        if not self.questions:
            messagebox.showerror("Erro", "Não foi possível gerar as perguntas.")
            self.show_file_selection_screen(simulado_name, chapter_name)
            return

        self.current_question_index = 0
        self.user_answers = []
        self.display_question()

    def display_question(self):
        self.clear_frame()
        q_data = self.questions[self.current_question_index]
        instruction = f"Marque {len(q_data['answer'])} resposta{'s' if len(q_data['answer']) > 1 else ''} correta{'s' if len(q_data['answer']) > 1 else ''}."

        Label(self.current_frame, text=f"Pergunta {self.current_question_index + 1}/{len(self.questions)}", font=("Helvetica", 14, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(anchor="w")
        Label(self.current_frame, text=q_data['question'], wraplength=850, justify="left", font=("Helvetica", 16), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(10, 20), anchor="w")
        Label(self.current_frame, text=instruction, font=("Helvetica", 12, "italic"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 15), anchor="w")

        self.option_vars, self.option_labels = [], []
        for option in q_data['options']:
            var = StringVar(value="")
            self.option_vars.append(var)
            cb = Checkbutton(self.current_frame, text=option, variable=var, onvalue=option, offvalue="", font=("Helvetica", 12), bg=self.get_color("bg"), fg=self.get_color("fg"), anchor="w", wraplength=800, justify="left", selectcolor=self.get_color("accent"))
            cb.pack(fill="x", pady=5)
            self.option_labels.append(cb)

        self.submit_button = Button(self.current_frame, text="Submeter Resposta", command=self.check_answer, font=("Helvetica", 12, "bold"), bg=self.get_color("button_bg"), fg=self.get_color("button_fg"))
        self.submit_button.pack(pady=20)

    def check_answer(self):
        self.submit_button.config(state="disabled")
        for cb in self.option_labels:
            cb.config(state="disabled")

        q_data = self.questions[self.current_question_index]
        selected_answers = sorted([v.get() for v in self.option_vars if v.get()])
        api_answer_letters = q_data["answer"]
        all_option_texts = q_data["options"]
        letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        correct_answers_text = sorted([all_option_texts[letter_map[l]] for l in api_answer_letters if l in letter_map])
        is_correct = (selected_answers == correct_answers_text)

        self.user_answers.append({
            "question": q_data["question"],
            "selected": selected_answers,
            "correct": correct_answers_text,
            "is_correct": is_correct
        })

        for cb in self.option_labels:
            is_correct_option = cb["text"] in correct_answers_text
            was_selected = cb["text"] in selected_answers
            if is_correct_option:
                cb.config(bg=self.get_color("correct_bg"), fg=self.get_color("correct_fg"), selectcolor=self.get_color("correct_bg"))
            elif was_selected and not is_correct_option:
                cb.config(bg=self.get_color("wrong_bg"), fg=self.get_color("wrong_fg"), selectcolor=self.get_color("wrong_bg"))

        explanation_frame = Frame(self.current_frame, bg=self.get_color("explanation_bg"), bd=1, relief="solid")
        explanation_frame.pack(fill="x", pady=10)
        Label(explanation_frame, text="Justificativa:", font=("Helvetica", 12, "bold"), bg=self.get_color("explanation_bg"), fg=self.get_color("fg")).pack(anchor="w", padx=10, pady=(5, 0))

        explanation_cue = q_data.get("explanation_cue", "")
        explanation_text = find_explanation_in_text(self.md_content, explanation_cue)

        explanation_widget = scrolledtext.ScrolledText(explanation_frame, wrap=tk.WORD, height=4, font=("Helvetica", 11), bg=self.get_color("explanation_bg"), fg=self.get_color("fg"), relief="flat")
        explanation_widget.insert(tk.END, explanation_text)
        explanation_widget.config(state="disabled")
        explanation_widget.pack(fill="x", expand=True, padx=10, pady=(0, 10))

        if self.current_question_index < len(self.questions) - 1:
            Button(self.current_frame, text="Próxima Pergunta →", command=self.next_question, font=("Helvetica", 12, "bold"), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=10)
        else:
            Button(self.current_frame, text="Ver Resultados Finais", command=self.show_final_results, font=("Helvetica", 12, "bold"), bg="#4CAF50", fg="white").pack(pady=10)

    def next_question(self):
        self.current_question_index += 1
        self.display_question()

    # -------- RESULTADOS --------
    def show_final_results(self):
        self.clear_frame()
        num_correct = sum(1 for ans in self.user_answers if ans["is_correct"])
        num_incorrect = len(self.questions) - num_correct

        Label(self.current_frame, text="Resultados Finais", font=("Helvetica", 24, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=20)
        Label(self.current_frame, text=f"Acertos: {num_correct}", font=("Helvetica", 18), fg="green", bg=self.get_color("bg")).pack()
        Label(self.current_frame, text=f"Erros: {num_incorrect}", font=("Helvetica", 18), fg="red", bg=self.get_color("bg")).pack()
        Label(self.current_frame, text=f"Total: {len(self.questions)}", font=("Helvetica", 18), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 20))

        self.save_logs_and_results(num_correct, num_incorrect)
        Button(self.current_frame, text="Ir para o Início", command=self.start_initial_screen, font=("Helvetica", 14, "bold"), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=20)

    def save_logs_and_results(self, acertos, erros):
        now = datetime.now()
        date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        timestamp_file = now.strftime("%Y%m%d_%H%M%S")

        sim_dir = os.path.join(ROOT_DIR, self.current_simulado)
        ensure_simulado_structure(sim_dir)
        logs_dir = os.path.join(sim_dir, LOGS_FOLDER_NAME)
        global_log = os.path.join(logs_dir, "log_global.txt")
        indiv_log = os.path.join(logs_dir, f"teste_{timestamp_file}.txt")
        results_csv = os.path.join(sim_dir, RESULTS_FILENAME)

        with open(global_log, "a", encoding="utf-8") as f:
            f.write(f"--- TESTE REALIZADO EM {date_str} {time_str} ---\n")
            f.write(f"Arquivo: {self.md_filename}\n")
            f.write(f"Resultado: {acertos} acertos, {erros} erros de {len(self.questions)} perguntas.\n\n")

        with open(indiv_log, "w", encoding="utf-8") as f:
            f.write(f"Relatório do Teste - {date_str} {time_str}\nArquivo Base: {self.md_filename}\n")
            for i, ans in enumerate(self.user_answers):
                f.write(f"P{i+1}: {ans['question']}\n R: {ans['selected']} | G: {ans['correct']} | {'OK' if ans['is_correct'] else 'X'}\n")

        with open(results_csv, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([self.md_filename, date_str, time_str, acertos, erros, len(self.questions)])

        messagebox.showinfo("Salvo!", f"Resultados salvos com sucesso.\nRelatório: {indiv_log}")

    # -------- DASHBOARD --------
    def show_dashboard(self, simulado_name):
        self.current_simulado = simulado_name
        sim_dir = os.path.join(ROOT_DIR, simulado_name)
        results_csv = os.path.join(sim_dir, RESULTS_FILENAME)

        self.clear_frame()
        Label(self.current_frame, text=f"Meu Progresso — {simulado_name}", font=("Helvetica", 24, "bold"), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=(0, 10))
        Button(self.current_frame, text="← Trocar Simulado", command=lambda: self.show_simulado_selection("dashboard"), font=("Helvetica", 12), bg=self.get_color("button_bg"), fg=self.get_color("button_fg")).pack(pady=(0, 10))

        try:
            df = pd.read_csv(results_csv)
            if df.empty:
                raise FileNotFoundError
        except (FileNotFoundError, pd.errors.EmptyDataError):
            Label(self.current_frame, text="Nenhum dado de resultado encontrado para este simulado.\nFaça um simulado para ver seu progresso!",
                  font=("Helvetica", 14), bg=self.get_color("bg"), fg=self.get_color("fg")).pack(pady=50)
            return

        main_canvas = Canvas(self.current_frame, bg=self.get_color("bg"))
        scrollbar = Scrollbar(self.current_frame, orient="vertical", command=main_canvas.yview)
        scrollable_frame = Frame(main_canvas, bg=self.get_color("bg"))
        scrollable_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # dados
        df["data"] = pd.to_datetime(df["data"])
        # extrai número do capítulo; se não achar, marca N/A
        df["capitulo"] = (df["arquivo_md"]
                          .str.extract(r'Capítulo\s+(\d+)')
                          .fillna(df["arquivo_md"].str.extract(r'(\d+)\.'))
                          .fillna("N/A"))
        df["percent_acerto"] = (df["acertos"] / df["total_perguntas"]) * 100

        # estatísticas
        stats_frame = Frame(scrollable_frame, bg=self.get_color("stats_bg"), bd=2, relief="groove")
        stats_frame.pack(pady=10, padx=10, fill="x")

        total_acertos = df["acertos"].sum()
        total_perguntas = df["total_perguntas"].sum()
        percent_total = (total_acertos / total_perguntas * 100) if total_perguntas > 0 else 0

        df_today = df[df["data"].dt.date == datetime.today().date()]
        acertos_hoje = df_today["acertos"].sum()
        perguntas_hoje = df_today["total_perguntas"].sum()
        percent_hoje = (acertos_hoje / perguntas_hoje * 100) if perguntas_hoje > 0 else 0

        Label(stats_frame, text=f"Acerto Total: {percent_total:.1f}%", font=("Helvetica", 14, "bold"), bg=self.get_color("stats_bg"), fg=self.get_color("fg")).pack()
        Label(stats_frame, text=f"Acerto Hoje: {percent_hoje:.1f}%", font=("Helvetica", 14, "bold"), bg=self.get_color("stats_bg"), fg=self.get_color("fg")).pack()

        # gráficos
        plt.style.use('seaborn-v0_8-whitegrid')

        # 1. Por arquivo/tópico
        df_by_file = df.groupby("arquivo_md")[["acertos", "erros"]].sum()
        fig1, ax1 = plt.subplots(figsize=(8, max(4, 0.5 * len(df_by_file))))
        df_by_file.plot(kind="barh", ax=ax1, color=["#28a745", "#dc3545"])
        ax1.set_title("Desempenho por Arquivo/Tópico")
        ax1.set_xlabel("Nº de Questões"); ax1.set_ylabel("")
        fig1.tight_layout(); fig1.subplots_adjust(left=0.4)
        FigureCanvasTkAgg(fig1, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill="x")

        # 2. Por capítulo
        df_by_chapter = df.groupby("capitulo")[["acertos", "erros"]].sum()
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        df_by_chapter.plot(kind="bar", ax=ax2, color=["#007bff", "#ffc107"])
        ax2.set_title("Desempenho por Capítulo")
        ax2.set_ylabel("Nº de Questões"); ax2.set_xlabel("Capítulo")
        plt.xticks(rotation=0); fig2.tight_layout()
        FigureCanvasTkAgg(fig2, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill="x")

        # 3. Progresso diário
        df_by_day = df.groupby(df["data"].dt.date)["percent_acerto"].mean()
        fig3, ax3 = plt.subplots(figsize=(8, 4))
        df_by_day.plot(kind="line", ax=ax3, marker="o", style="-")
        ax3.set_title("Progresso Diário (% de Acerto)")
        ax3.set_ylabel("% de Acerto"); ax3.set_xlabel("Data"); ax3.set_ylim(0, 105)
        plt.xticks(rotation=45); fig3.tight_layout()
        FigureCanvasTkAgg(fig3, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill="x")

        # 4. Por hora do dia
        df["hora"] = pd.to_datetime(df["hora"], format="%H:%M:%S").dt.hour
        df_by_hour = df.groupby("hora")["percent_acerto"].mean()
        fig4, ax4 = plt.subplots(figsize=(8, 4))
        df_by_hour.plot(kind="bar", ax=ax4)
        ax4.set_title("Média de Acerto por Hora do Dia")
        ax4.set_ylabel("% de Acerto"); ax4.set_xlabel("Hora do Dia"); ax4.set_ylim(0, 105)
        plt.xticks(rotation=0); fig4.tight_layout()
        FigureCanvasTkAgg(fig4, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill="x")

# -------------------------- MAIN --------------------------
if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY"):
        messagebox.showerror("Configuração Necessária", "DEEPSEEK_API_KEY não encontrada.\nCrie um arquivo '.env' e adicione a chave.")
    else:
        try:
            import pandas as _p; import matplotlib.pyplot as _m
        except ImportError:
            messagebox.showerror("Bibliotecas Faltando", "As bibliotecas 'pandas' e 'matplotlib' são necessárias.\nInstale-as com: pip install pandas matplotlib")
        else:
            root = tk.Tk()
            app = QuizApp(root)
            root.mainloop()
