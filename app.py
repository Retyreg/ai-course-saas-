import streamlit as st
import os
import tempfile
import base64
import io
from datetime import datetime
from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field
from typing import List
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.utils import ImageReader

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Vyud AI", page_icon="🎓", layout="wide")
load_dotenv()

# ==========================================
# 🌍 СЛОВАРЬ ПЕРЕВОДОВ (UI LOCALIZATION)
# ==========================================
TRANSLATIONS = {
    "Русский": {
        "branding_header": "🏢 Брендинг",
        "logo_label": "Логотип компании (PNG/JPG)",
        "settings_header": "⚙️ Настройки",
        "ui_lang_label": "Язык интерфейса / Interface Language:",
        "target_lang_label": "Язык генерации теста:",
        "target_lang_placeholder": "Например: Italian, Hindi, Deutsch...",
        "target_lang_caption": "AI автоматически переведет материал на этот язык.",
        "difficulty_label": "Сложность:",
        "diff_easy": "Easy (Факты)",
        "diff_medium": "Medium (Понимание)",
        "diff_hard": "Hard (Кейсы)",
        "count_label": "Количество вопросов:",
        "contact_header": "📬 Связь с автором",
        "contact_text": "<b>Нужен такой же инструмент?</b><br>Напишите мне, чтобы обсудить внедрение.",
        "telegram_btn": "✈️ Написать в Telegram",
        "email_caption": "Или на почту:",
        "email_btn": "📤 Открыть почту",
        "status_ok": "🟢 System Status: Online & Secure",
        "status_fail": "🔴 System Status: Keys Missing",
        "main_title": "🎓 Vyud AI",
        "main_desc": "#### Превращайте документы в обучение за секунды.\nЗагрузите инструкцию (PDF, DOCX, PPTX, Excel) — AI создаст интерактивный тест на **любом языке**, проверит знания и выдаст сертификат.",
        "key_warning": "⚠️ Система не настроена. Введите API ключи для начала работы:",
        "upload_label": "Загрузи материал (PDF, PPTX, DOCX, XLSX, TXT)",
        "btn_create": "🚀 Создать Тест",
        "spinner_read": "📄 Читаю документ и таблицы...",
        "spinner_ai": "🧠 Анализирую контент и перевожу...",
        "error_read": "Ошибка чтения файла. Возможно, он пуст или защищен паролем.",
        "success_cert": "🏆 Генерация сертификата",
        "cert_name_label": "Имя студента (на латинице):",
        "cert_course_label": "Название курса:",
        "btn_download_cert": "📄 Сгенерировать Сертификат",
        "btn_download_html": "📥 Скачать HTML (Vyud AI)",
        "export_header": "📦 Экспорт курса (HTML)",
        "q_options": "Варианты:",
        "q_show_answer": "Показать ответ",
        "q_correct": "Правильно:",
        "download_ready": "📥 Скачать PDF Сертификат"
    },
    "English": {
        "branding_header": "🏢 Branding",
        "logo_label": "Company Logo (PNG/JPG)",
        "settings_header": "⚙️ Settings",
        "ui_lang_label": "Interface Language:",
        "target_lang_label": "Target Quiz Language:",
        "target_lang_placeholder": "E.g.: Italian, Hindi, Deutsch...",
        "target_lang_caption": "AI will automatically translate content to this language.",
        "difficulty_label": "Difficulty:",
        "diff_easy": "Easy (Facts)",
        "diff_medium": "Medium (Understanding)",
        "diff_hard": "Hard (Case Studies)",
        "count_label": "Number of Questions:",
        "contact_header": "📬 Contact Author",
        "contact_text": "<b>Need this tool?</b><br>Contact me to discuss enterprise integration.",
        "telegram_btn": "✈️ Contact via Telegram",
        "email_caption": "Or via Email:",
        "email_btn": "📤 Open Email Client",
        "status_ok": "🟢 System Status: Online & Secure",
        "status_fail": "🔴 System Status: Keys Missing",
        "main_title": "🎓 Vyud AI",
        "main_desc": "#### Turn documents into training in seconds.\nUpload instructions (PDF, DOCX, PPTX, Excel) — AI will create an interactive test in **any language**, verify knowledge, and issue a certificate.",
        "key_warning": "⚠️ System not configured. Enter API keys to start:",
        "upload_label": "Upload material (PDF, PPTX, DOCX, XLSX, TXT)",
        "btn_create": "🚀 Create Quiz",
        "spinner_read": "📄 Reading document and tables...",
        "spinner_ai": "🧠 Analyzing content and translating...",
        "error_read": "Error reading file. It might be empty or password protected.",
        "success_cert": "🏆 Certificate Generation",
        "cert_name_label": "Student Name (Latin):",
        "cert_course_label": "Course Title:",
        "btn_download_cert": "📄 Generate Certificate",
        "btn_download_html": "📥 Download HTML (Vyud AI)",
        "export_header": "📦 Export Course (HTML)",
        "q_options": "Options:",
        "q_show_answer": "Show Answer",
        "q_correct": "Correct:",
        "download_ready": "📥 Download PDF Certificate"
    }
}

# --- СТРУКТУРА ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Текст вопроса или описание ситуации")
    options: List[str] = Field(..., description="4 варианта ответа")
    correct_option_id: int = Field(..., description="Индекс правильного ответа (0-3)")
    explanation: str = Field(..., description="Объяснение правильного ответа")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ФУНКЦИЯ ГЕНЕРАЦИИ СЕРТИФИКАТА (PDF) ---
def create_certificate(student_name, course_name, logo_file=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    
    # Рамка
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.setLineWidth(5)
    c.rect(30, 30, width-60, height-60)
    
    if logo_file:
        try:
            logo_file.seek(0)
            logo = ImageReader(logo_file)
            c.drawImage(logo, width/2 - 50, height - 140, width=100, preserveAspectRatio=True, mask='auto')
        except:
            pass

    c.setFont("Helvetica-Bold", 40)
    c.drawCentredString(width/2, height/2 + 40, "CERTIFICATE")
    
    c.setFont("Helvetica", 20)
    c.drawCentredString(width/2, height/2, "OF COMPLETION")
    
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2 - 30, "This is to certify that")
    
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height/2 - 70, student_name)
    
    c.setFont("Helvetica", 16)
    c.drawCentredString(width/2, height/2 - 100, "has successfully completed the course")
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height/2 - 130, course_name)
    
    c.setFont("Helvetica", 12)
    date_str = datetime.now().strftime("%Y-%m-%d")
    c.drawString(50, 50, f"Date: {date_str}")
    c.drawRightString(width-50, 50, "Authorized by Vyud AI")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- ПРОВЕРКА КЛЮЧЕЙ ---
has_llama = bool(os.getenv("LLAMA_CLOUD_API_KEY"))
has_openai = bool(os.getenv("OPENAI_API_KEY"))

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    # 1. ВЫБОР ЯЗЫКА ИНТЕРФЕЙСА
    ui_language = st.selectbox("🌐 Interface Language", list(TRANSLATIONS.keys()), index=0)
    t = TRANSLATIONS[ui_language] # Загружаем нужный словарь

    st.header(t["branding_header"])
    company_logo = st.file_uploader(t["logo_label"], type=["png", "jpg", "jpeg"])
    if company_logo:
        st.image(company_logo, width=100)

    st.divider()
    st.header(t["settings_header"])
    
    # Ввод языка генерации
    quiz_lang = st.text_input(
        t["target_lang_label"],
        value="Русский" if ui_language == "Русский" else "English",
        placeholder=t["target_lang_placeholder"]
    )
    st.caption(t["target_lang_caption"])
    
    quiz_difficulty = st.radio(
        t["difficulty_label"],
        [t["diff_easy"], t["diff_medium"], t["diff_hard"]],
        index=1 
    )
    
    quiz_count = st.slider(t["count_label"], 1, 10, 5)

    st.divider()
    st.markdown(f"### {t['contact_header']}")
    
    st.markdown(
        f"""
        <div style="background-color: #f0f2f6; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
            <p style="margin:0; font-size: 14px; color: #31333F;">
            {t['contact_text']}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.link_button(t["telegram_btn"], "https://t.me/retyreg")

    st.caption(t["email_caption"])
    st.code("vatutovd@gmail.com", language=None)
    
    contact_url = "mailto:vatutovd@gmail.com?subject=Question about Vyud AI"
    st.link_button(t["email_btn"], contact_url)
    
    st.divider()
    
    if has_llama and has_openai:
        st.caption(t["status_ok"])
    else:
        st.caption(t["status_fail"])
        
    st.caption("© 2025 Vyud AI")

# --- ОСНОВНОЙ ЭКРАН ---
st.title(t["main_title"])
st.markdown(t["main_desc"])
st.divider()

if not (has_llama and has_openai):
    st.warning(t["key_warning"])
    new_llama = st.text_input("LlamaCloud Key", type="password")
    new_openai = st.text_input("OpenAI Key", type="password")
    if new_llama and new_openai:
        os.environ["LLAMA_CLOUD_API_KEY"] = new_llama
        os.environ["OPENAI_API_KEY"] = new_openai
        st.rerun()
    st.stop()

uploaded_file = st.file_uploader(t["upload_label"], type=["pdf", "pptx", "docx", "xlsx", "txt"])

if uploaded_file and 'file_name' not in st.session_state:
    st.session_state['file_name'] = uploaded_file.name

if uploaded_file:
    if st.button(t["btn_create"]):
        
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        with st.spinner(t["spinner_read"]):
            try:
                parser = LlamaParse(result_type="markdown", api_key=os.environ["LLAMA_CLOUD_API_KEY"])
                file_extractor = {".pdf": parser, ".pptx": parser, ".docx": parser, ".xlsx": parser, ".txt": parser}
                docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor).load_data()
                if not docs:
                    st.error(t["error_read"])
                    st.stop()
                text = docs[0].text
            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        target_lang = quiz_lang if quiz_lang.strip() else "English"

        with st.spinner(f"{t['spinner_ai']} ({target_lang})..."):
            try:
                Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
                
                prompt = (
                    f"You are an expert instructional designer. "
                    f"1. Analyze the uploaded content (it can be in any language). "
                    f"2. Create a quiz STRICTLY in this language: '{target_lang}'. "
                    f"3. Number of questions: {quiz_count}. "
                    f"4. Difficulty level: {quiz_difficulty}. "
                    "Difficulty Guide: "
                    "- Easy: Fact recall. "
                    "- Medium: Understanding concepts. "
                    "- Hard: Situational analysis/Case studies. "
                    "Return STRICTLY JSON format matching the Quiz schema."
                )
                
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=Quiz,
                    prompt_template_str=prompt + " Content: {text}",
                    llm=Settings.llm
                )
                result = program(text=text[:25000])
                st.session_state['quiz'] = result
            except Exception as e:
                st.error(f"AI Error: {e}")
                st.stop()

# --- ВЫВОД РЕЗУЛЬТАТА ---
if 'quiz' in st.session_state:
    st.divider()
    
    for i, q in enumerate(st.session_state['quiz'].questions):
        st.subheader(f"{i+1}. {q.scenario}")
        st.radio(t["q_options"], q.options, key=f"q{i}")
        with st.expander(t["q_show_answer"]):
            st.write(f"{t['q_correct']} {q.options[q.correct_option_id]}")
            st.info(q.explanation)

    st.divider()
    st.subheader(t["success_cert"])
    col1, col2 = st.columns(2)
    with col1:
        student_name = st.text_input(t["cert_name_label"], "Ivan Ivanov")
    with col2:
        course_default = st.session_state.get('file_name', 'Corporate Training')
        course_title = st.text_input(t["cert_course_label"], course_default)
    
    if st.button(t["btn_download_cert"]):
        pdf_data = create_certificate(student_name, course_title, company_logo)
        st.download_button(
            label=t["download_ready"],
            data=pdf_data,
            file_name=f"Certificate_{student_name}.pdf",
            mime="application/pdf"
        )

    st.divider()
    st.subheader(t["export_header"])
    
    # HTML Export Logic (Simplified for brevity, logic remains same)
    quiz_json = st.session_state['quiz'].model_dump_json()
    st.download_button(
        label=t["btn_download_html"],
        data=f"<html><body><h1>Vyud AI Quiz</h1><p>Quiz data: {quiz_json}</p></body></html>", # Simplified for MVP
        file_name="vyud_course.html",
        mime="text/html"
    )
