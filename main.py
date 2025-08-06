# main.py
import tkinter as tk
from tkinter import messagebox, Frame, Label, Button, Checkbutton, StringVar, scrolledtext, Canvas, Scrollbar
import os
import json
from datetime import datetime
import csv
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- CONFIGURAÇÃO INICIAL ---

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do cliente da API DeepSeek
try:
    client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
except Exception as e:
    print(f"Erro ao inicializar o cliente da API: {e}")
    client = None

# --- ESTRUTURA DE DIRETÓRIOS ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(ROOT_DIR, 'conteudo')
LOGS_DIR = os.path.join(ROOT_DIR, 'logs')
RESULTS_CSV = os.path.join(ROOT_DIR, 'results.csv')
GLOBAL_LOG_TXT = os.path.join(LOGS_DIR, 'log_global.txt')

# Garante que as pastas e arquivos necessários existam
os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Cria o arquivo CSV com cabeçalho se não existir
if not os.path.exists(RESULTS_CSV):
    with open(RESULTS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['arquivo_md', 'data', 'hora', 'acertos', 'erros', 'total_perguntas'])


# --- FUNÇÕES DE LÓGICA ---

def get_chapters():
    """Busca os diretórios de capítulos dentro da pasta 'conteudo'."""
    try:
        dirs = [d for d in os.listdir(CONTENT_DIR) if os.path.isdir(os.path.join(CONTENT_DIR, d))]
        return sorted(dirs, key=lambda x: int(x) if x.isdigit() else x)
    except FileNotFoundError:
        return []

def get_md_files(chapter_name):
    """Busca os arquivos .md dentro de um diretório de capítulo."""
    chapter_path = os.path.join(CONTENT_DIR, chapter_name)
    try:
        return sorted([f for f in os.listdir(chapter_path) if f.endswith('.md')])
    except FileNotFoundError:
        return []

def get_md_content(chapter_name, file_name):
    """Lê o conteúdo de um arquivo .md específico."""
    file_path = os.path.join(CONTENT_DIR, chapter_name, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None

def get_all_md_content_from_chapter(chapter_name):
    """Lê e concatena o conteúdo de todos os arquivos .md de um capítulo."""
    all_content = []
    md_files = get_md_files(chapter_name)
    for file_name in md_files:
        content = get_md_content(chapter_name, file_name)
        if content:
            all_content.append(content)
    return "\n\n---\n\n".join(all_content)

def generate_questions_from_api(content):
    """Chama a API do DeepSeek para gerar 5 perguntas em formato JSON."""
    if not client:
        messagebox.showerror("Erro de API", "O cliente da API não foi inicializado.")
        return None

    prompt = f"""
    Com base no conteúdo fornecido abaixo, gere exatamente 10 perguntas de múltipla escolha.
    O formato da resposta DEVE ser um JSON válido, contendo uma lista de 10 objetos.
    Cada objeto deve ter as seguintes chaves:
    - "question": A pergunta (string).
    - "options": Uma lista de 4 alternativas (strings).
    - "answer": Uma lista contendo a(s) resposta(s) correta(s) (strings).
    - "explanation_cue": Uma frase curta extraída diretamente do texto que justifica a resposta correta.
    --- CONTEÚDO PARA ANÁLISE ---
    {content}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[
                {"role": "system", "content": "Você é um assistente especialista em criar testes sobre Conceitos de dados do Azure, para que seu usuario demonstre o conhecimento fundamental dos principais conceitos de dados relacionados aos serviços de dados do Microsoft Azure."},
                {"role": "user", "content": prompt},
            ],
            stream=False, temperature=0.7, max_tokens=2048
        )
        json_response = response.choices[0].message.content.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(json_response)
    except Exception as e:
        messagebox.showerror("Erro de API", f"Ocorreu um erro: {e}")
        return None

def find_explanation_in_text(full_text, cue):
    """Encontra o parágrafo no texto original que contém a pista da explicação."""
    paragraphs = full_text.split('\n\n')
    for p in paragraphs:
        if cue in p:
            return p.strip()
    return "Contexto não encontrado no texto original."

# --- CLASSE DA APLICAÇÃO (GUI com Tkinter) ---

class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SimuladoMD - Gerador de Testes")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f0f0")
        self.current_frame = None
        self.start_initial_screen()

    def clear_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = Frame(self.root, bg="#f0f0f0")
        self.current_frame.pack(fill="both", expand=True, padx=20, pady=20)

    def start_initial_screen(self):
        """Exibe a tela inicial para seleção de capítulo ou visualização de progresso."""
        self.clear_frame()
        Label(self.current_frame, text="Bem-vindo ao SimuladoMD!", font=("Helvetica", 24, "bold"), bg="#f0f0f0").pack(pady=(10, 20))
        Label(self.current_frame, text="Escolha uma opção:", font=("Helvetica", 14), bg="#f0f0f0").pack(pady=(0, 20), anchor="w")

        Button(self.current_frame, text="🚀 Iniciar Novo Simulado", font=("Helvetica", 12, "bold"), command=self.show_chapter_selection_screen, width=40, height=2, bg="#cce5ff").pack(pady=10)
        Button(self.current_frame, text="📊 Ver Meu Progresso", font=("Helvetica", 12, "bold"), command=self.show_dashboard, width=40, height=2, bg="#d4edda").pack(pady=10)

    def show_chapter_selection_screen(self):
        """Exibe a tela para seleção de capítulo (pasta)."""
        self.clear_frame()
        Label(self.current_frame, text="1. Escolha um capítulo:", font=("Helvetica", 14), bg="#f0f0f0").pack(pady=(0, 20), anchor="w")

        chapters = get_chapters()
        if not chapters:
            Label(self.current_frame, text="Nenhum capítulo encontrado na pasta 'conteudo'.", font=("Helvetica", 12), fg="red", bg="#f0f0f0").pack()
        else:
            for chapter in chapters:
                btn = Button(self.current_frame, text=f"Capítulo {chapter}", font=("Helvetica", 12), command=lambda c=chapter: self.show_file_selection_screen(c), width=40, height=2)
                btn.pack(pady=5)
        
        Button(self.current_frame, text="← Voltar ao Início", command=self.start_initial_screen, font=("Helvetica", 12)).pack(pady=(20, 0))

    def show_file_selection_screen(self, chapter_name):
        """Mostra os arquivos .md dentro do capítulo selecionado e a opção para o capítulo inteiro."""
        self.clear_frame()
        Label(self.current_frame, text=f"Capítulo {chapter_name}", font=("Helvetica", 24, "bold"), bg="#f0f0f0").pack(pady=(10, 20))
        Label(self.current_frame, text="2. Escolha uma opção:", font=("Helvetica", 14), bg="#f0f0f0").pack(pady=(0, 10), anchor="w")

        Button(self.current_frame, text="▶ Gerar teste do capítulo inteiro", font=("Helvetica", 12, "bold"), command=lambda: self.start_quiz(chapter_name), bg="#d0e0ff").pack(pady=(5, 15), fill="x", ipady=5)
        Label(self.current_frame, text="Ou escolha um arquivo específico:", font=("Helvetica", 12, "italic"), bg="#f0f0f0").pack(pady=(0, 10), anchor="w")

        md_files = get_md_files(chapter_name)
        if not md_files:
            Label(self.current_frame, text="Nenhum arquivo .md encontrado.", font=("Helvetica", 12), fg="red", bg="#f0f0f0").pack()
        else:
            for md_file in md_files:
                Button(self.current_frame, text=md_file, font=("Helvetica", 12), command=lambda f=md_file: self.start_quiz(chapter_name, f), wraplength=500, justify="left").pack(pady=5, fill="x")
        
        Button(self.current_frame, text="← Voltar para Capítulos", command=self.show_chapter_selection_screen, font=("Helvetica", 12)).pack(pady=(20, 0), anchor="s")

    def start_quiz(self, chapter_name, file_name=None):
        """Inicia o quiz para um arquivo específico ou para o capítulo inteiro."""
        self.clear_frame()
        Label(self.current_frame, text="Gerando perguntas...\nAguarde um momento.", font=("Helvetica", 16), bg="#f0f0f0").pack(pady=50)
        self.root.update()

        self.md_filename = f"Capítulo {chapter_name} (Completo)" if not file_name else file_name
        self.md_content = get_all_md_content_from_chapter(chapter_name) if not file_name else get_md_content(chapter_name, file_name)

        if not self.md_content:
            messagebox.showerror("Erro", f"Não foi possível encontrar conteúdo para '{self.md_filename}'.")
            self.show_file_selection_screen(chapter_name)
            return

        self.questions = generate_questions_from_api(self.md_content)
        if not self.questions or len(self.questions) == 0:
            messagebox.showerror("Erro", "Não foi possível gerar as perguntas.")
            self.show_file_selection_screen(chapter_name)
            return

        self.current_question_index = 0
        self.user_answers = []
        self.display_question()

    def display_question(self):
        """Exibe a pergunta atual e suas opções."""
        self.clear_frame()
        q_data = self.questions[self.current_question_index]
        instruction = f"Marque {len(q_data['answer'])} resposta{'s' if len(q_data['answer']) > 1 else ''} correta{'s' if len(q_data['answer']) > 1 else ''}."

        Label(self.current_frame, text=f"Pergunta {self.current_question_index + 1}/{len(self.questions)}", font=("Helvetica", 14, "bold"), bg="#f0f0f0").pack(anchor="w")
        Label(self.current_frame, text=q_data['question'], wraplength=850, justify="left", font=("Helvetica", 16), bg="#f0f0f0").pack(pady=(10, 20), anchor="w")
        Label(self.current_frame, text=instruction, font=("Helvetica", 12, "italic"), bg="#f0f0f0").pack(pady=(0, 15), anchor="w")

        self.option_vars = []
        self.option_labels = []
        for option in q_data['options']:
            var = StringVar(value="")
            self.option_vars.append(var)
            cb = Checkbutton(self.current_frame, text=option, variable=var, onvalue=option, offvalue="", font=("Helvetica", 12), bg="#f0f0f0", anchor="w", wraplength=800, justify="left")
            cb.pack(fill="x", pady=5)
            self.option_labels.append(cb)

        self.submit_button = Button(self.current_frame, text="Submeter Resposta", command=self.check_answer, font=("Helvetica", 12, "bold"))
        self.submit_button.pack(pady=20)

    def check_answer(self):
        """Verifica a resposta do usuário, exibe o resultado e a explicação."""
        self.submit_button.config(state="disabled")
        for cb in self.option_labels: cb.config(state="disabled")

        selected_answers = sorted([var.get() for var in self.option_vars if var.get()])
        correct_answers = sorted(self.questions[self.current_question_index]['answer'])
        
        self.user_answers.append({
            "question": self.questions[self.current_question_index]['question'],
            "selected": selected_answers,
            "correct": correct_answers,
            "is_correct": (selected_answers == correct_answers)
        })

        # Pinta o fundo das respostas para dar feedback visual
        for cb in self.option_labels:
            is_correct_option = cb['text'] in correct_answers
            was_selected = cb['text'] in selected_answers

            if is_correct_option:
                # Pinta a opção correta de verde
                cb.config(bg="#d4edda", fg="#155724", selectcolor="#d4edda")
            elif was_selected and not is_correct_option:
                # Pinta a seleção incorreta do usuário de vermelho
                cb.config(bg="#f8d7da", fg="#721c24", selectcolor="#f8d7da")

        explanation_frame = Frame(self.current_frame, bg="#e0e0e0", bd=1, relief="solid")
        explanation_frame.pack(fill="x", pady=10)
        Label(explanation_frame, text="Justificativa:", font=("Helvetica", 12, "bold"), bg="#e0e0e0").pack(anchor="w", padx=10, pady=(5,0))
        
        explanation_cue = self.questions[self.current_question_index].get('explanation_cue', '')
        explanation_text = find_explanation_in_text(self.md_content, explanation_cue)
        
        explanation_widget = scrolledtext.ScrolledText(explanation_frame, wrap=tk.WORD, height=4, font=("Helvetica", 11), bg="#e0e0e0", relief="flat")
        explanation_widget.insert(tk.END, explanation_text)
        explanation_widget.config(state="disabled")
        explanation_widget.pack(fill="x", expand=True, padx=10, pady=(0,10))

        if self.current_question_index < len(self.questions) - 1:
            Button(self.current_frame, text="Próxima Pergunta →", command=self.next_question, font=("Helvetica", 12, "bold")).pack(pady=10)
        else:
            Button(self.current_frame, text="Ver Resultados Finais", command=self.show_final_results, font=("Helvetica", 12, "bold"), bg="#4CAF50", fg="white").pack(pady=10)

    def next_question(self):
        self.current_question_index += 1
        self.display_question()

    def show_final_results(self):
        self.clear_frame()
        num_correct = sum(1 for ans in self.user_answers if ans['is_correct'])
        num_incorrect = len(self.questions) - num_correct
        
        Label(self.current_frame, text="Resultados Finais", font=("Helvetica", 24, "bold"), bg="#f0f0f0").pack(pady=20)
        Label(self.current_frame, text=f"Acertos: {num_correct}", font=("Helvetica", 18), fg="green", bg="#f0f0f0").pack()
        Label(self.current_frame, text=f"Erros: {num_incorrect}", font=("Helvetica", 18), fg="red", bg="#f0f0f0").pack()
        Label(self.current_frame, text=f"Total: {len(self.questions)}", font=("Helvetica", 18), bg="#f0f0f0").pack(pady=(0, 20))

        self.save_logs_and_results(num_correct, num_incorrect)
        Button(self.current_frame, text="Ir para o Início", command=self.start_initial_screen, font=("Helvetica", 14, "bold")).pack(pady=20)

    def save_logs_and_results(self, acertos, erros):
        now = datetime.now()
        date_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        timestamp_file = now.strftime("%Y%m%d_%H%M%S")

        with open(GLOBAL_LOG_TXT, 'a', encoding='utf-8') as f:
            f.write(f"--- TESTE REALIZADO EM {date_str} {time_str} ---\n")
            f.write(f"Arquivo: {self.md_filename}\n")
            f.write(f"Resultado: {acertos} acertos, {erros} erros de {len(self.questions)} perguntas.\n\n")

        individual_log_filename = os.path.join(LOGS_DIR, f"teste_{timestamp_file}.txt")
        with open(individual_log_filename, 'w', encoding='utf-8') as f:
            f.write(f"Relatório do Teste - {date_str} {time_str}\nArquivo Base: {self.md_filename}\n")
            for i, ans in enumerate(self.user_answers):
                f.write(f"P{i+1}: {ans['question']}\n  R: {ans['selected']} | G: {ans['correct']} | {'OK' if ans['is_correct'] else 'X'}\n")

        with open(RESULTS_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([self.md_filename, date_str, time_str, acertos, erros, len(self.questions)])
        
        messagebox.showinfo("Salvo!", f"Resultados salvos com sucesso.\nRelatório: {individual_log_filename}")

    def show_dashboard(self):
        """Exibe o painel de progresso com estatísticas e gráficos."""
        self.clear_frame()
        
        Label(self.current_frame, text="Meu Progresso", font=("Helvetica", 24, "bold"), bg="#f0f0f0").pack(pady=(0, 10))
        Button(self.current_frame, text="← Voltar ao Início", command=self.start_initial_screen, font=("Helvetica", 12)).pack(pady=(0, 10))

        try:
            df = pd.read_csv(RESULTS_CSV)
            if df.empty:
                raise FileNotFoundError
        except (FileNotFoundError, pd.errors.EmptyDataError):
            Label(self.current_frame, text="Nenhum dado de resultado encontrado.\nFaça um simulado para ver seu progresso!", font=("Helvetica", 14), bg="#f0f0f0").pack(pady=50)
            return

        # Prepara um canvas com scroll para comportar todos os gráficos
        main_canvas = Canvas(self.current_frame, bg="#f0f0f0")
        scrollbar = Scrollbar(self.current_frame, orient="vertical", command=main_canvas.yview)
        scrollable_frame = Frame(main_canvas, bg="#f0f0f0")

        scrollable_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Processamento de Dados ---
        df['data'] = pd.to_datetime(df['data'])
        df['capitulo'] = df['arquivo_md'].str.extract(r'Capítulo (\d+)').fillna(df['arquivo_md'].str.extract(r'(\d+)\.')).fillna('N/A')
        df['percent_acerto'] = (df['acertos'] / df['total_perguntas']) * 100

        # --- Estatísticas ---
        stats_frame = Frame(scrollable_frame, bg="#e9ecef", bd=2, relief="groove")
        stats_frame.pack(pady=10, padx=10, fill="x")
        
        total_acertos = df['acertos'].sum()
        total_perguntas = df['total_perguntas'].sum()
        percent_total = (total_acertos / total_perguntas * 100) if total_perguntas > 0 else 0
        
        df_today = df[df['data'].dt.date == datetime.today().date()]
        acertos_hoje = df_today['acertos'].sum()
        perguntas_hoje = df_today['total_perguntas'].sum()
        percent_hoje = (acertos_hoje / perguntas_hoje * 100) if perguntas_hoje > 0 else 0
        
        Label(stats_frame, text=f"Acerto Total: {percent_total:.1f}%", font=("Helvetica", 14, "bold"), bg="#e9ecef").pack()
        Label(stats_frame, text=f"Acerto Hoje: {percent_hoje:.1f}%", font=("Helvetica", 14, "bold"), bg="#e9ecef").pack()

        # --- Gráficos ---
        plt.style.use('seaborn-v0_8-whitegrid')
        
        # 1. Acertos e Erros por Arquivo
        df_by_file = df.groupby('arquivo_md')[['acertos', 'erros']].sum()
        fig1, ax1 = plt.subplots(figsize=(8, max(4, 0.5 * len(df_by_file))))
        df_by_file.plot(kind='barh', ax=ax1, color=['#28a745', '#dc3545'])
        ax1.set_title('Desempenho por Arquivo/Tópico')
        ax1.set_xlabel('Nº de Questões')
        ax1.set_ylabel('')
        fig1.tight_layout()
        # Ajuste extra para garantir que os rótulos não sejam cortados
        fig1.subplots_adjust(left=0.4)
        FigureCanvasTkAgg(fig1, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill='x')

        # 2. Acertos e Erros por Capítulo
        df_by_chapter = df.groupby('capitulo')[['acertos', 'erros']].sum()
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        df_by_chapter.plot(kind='bar', ax=ax2, color=['#007bff', '#ffc107'])
        ax2.set_title('Desempenho por Capítulo')
        ax2.set_ylabel('Nº de Questões')
        ax2.set_xlabel('Capítulo')
        plt.xticks(rotation=0)
        fig2.tight_layout()
        FigureCanvasTkAgg(fig2, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill='x')

        # 3. Progresso ao longo dos dias
        df_by_day = df.groupby(df['data'].dt.date)['percent_acerto'].mean()
        fig3, ax3 = plt.subplots(figsize=(8, 4))
        df_by_day.plot(kind='line', ax=ax3, marker='o', style='-')
        ax3.set_title('Progresso Diário (% de Acerto)')
        ax3.set_ylabel('% de Acerto')
        ax3.set_xlabel('Data')
        ax3.set_ylim(0, 105)
        plt.xticks(rotation=45)
        fig3.tight_layout()
        FigureCanvasTkAgg(fig3, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill='x')

        # 4. Progresso ao longo das horas
        df['hora'] = pd.to_datetime(df['hora'], format='%H:%M:%S').dt.hour
        df_by_hour = df.groupby('hora')['percent_acerto'].mean()
        fig4, ax4 = plt.subplots(figsize=(8, 4))
        df_by_hour.plot(kind='bar', ax=ax4)
        ax4.set_title('Média de Acerto por Hora do Dia')
        ax4.set_ylabel('% de Acerto')
        ax4.set_xlabel('Hora do Dia')
        ax4.set_ylim(0, 105)
        plt.xticks(rotation=0)
        fig4.tight_layout()
        FigureCanvasTkAgg(fig4, master=scrollable_frame).get_tk_widget().pack(pady=10, padx=10, fill='x')


# --- EXECUÇÃO PRINCIPAL ---
if __name__ == "__main__":
    if not os.getenv("DEEPSEEK_API_KEY"):
        messagebox.showerror("Configuração Necessária", "DEEPSEEK_API_KEY não encontrada.\nCrie um arquivo '.env' e adicione a chave.")
    else:
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
        except ImportError:
            messagebox.showerror("Bibliotecas Faltando", "As bibliotecas 'pandas' e 'matplotlib' são necessárias.\nInstale-as com: pip install pandas matplotlib")
        else:
            root = tk.Tk()
            app = QuizApp(root)
            root.mainloop()
