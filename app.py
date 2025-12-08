import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader, Settings
from llama_index.llms.openai import OpenAI
from llama_index.core.program import LLMTextCompletionProgram
from pydantic import BaseModel, Field
from typing import List

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="AI Course Factory", page_icon="🎓", layout="wide")
load_dotenv()

# --- СТРУКТУРА ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Описание ситуации")
    options: List[str] = Field(..., description="4 варианта ответа")
    correct_option_id: int = Field(..., description="Индекс правильного ответа (0-3)")
    explanation: str = Field(..., description="Объяснение")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Выбор языка (Включая Узбекский и Кыргызский)
    quiz_lang = st.selectbox(
        "Язык теста:",
        ["Русский", "English", "Қазақша", "O'zbekcha", "Кыргызча", "Español", "Deutsch"],
        index=0
    )
    
    # Сложность
    quiz_difficulty = st.radio(
        "Сложность:",
        ["Easy (Факты)", "Hard (Кейсы)"],
        index=1
    )
    
    # Количество вопросов
    quiz_count = st.slider("Количество вопросов:", 1, 10, 3)

# --- ОСНОВНОЙ ЭКРАН ---
st.title("🎓 AI Course Generator")

# БЕЗОПАСНАЯ ПРОВЕРКА КЛЮЧЕЙ
has_llama = bool(os.getenv("LLAMA_CLOUD_API_KEY"))
has_openai = bool(os.getenv("OPENAI_API_KEY"))

if has_llama and has_openai:
    st.success("✅ Ключи активны (Secure Mode)")
else:
    st.warning("⚠️ Ключи не найдены. Введите их (они не будут сохранены в браузере):")
    new_llama = st.text_input("LlamaCloud Key", type="password")
    new_openai = st.text_input("OpenAI Key", type="password")
    
    if new_llama and new_openai:
        os.environ["LLAMA_CLOUD_API_KEY"] = new_llama
        os.environ["OPENAI_API_KEY"] = new_openai
        st.rerun()

uploaded_file = st.file_uploader("Загрузи инструкцию (PDF)", type=["pdf"])

if uploaded_file:
    if st.button("🚀 Создать Тест"):
        
        # Проверка ключей перед стартом
        if not os.environ.get("LLAMA_CLOUD_API_KEY"):
            st.error("Нет ключей!")
            st.stop()

        # 1. Сохраняем файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        # 2. Парсим
        with st.spinner("📄 Читаю документ..."):
            try:
                parser = LlamaParse(result_type="markdown", language="ru", api_key=os.environ["LLAMA_CLOUD_API_KEY"])
                docs = SimpleDirectoryReader(input_files=[tmp_path], file_extractor={".pdf": parser}).load_data()
                if not docs:
                    st.error("Ошибка чтения файла.")
                    st.stop()
                text = docs[0].text
            except Exception as e:
                st.error(f"Ошибка парсинга: {e}")
                st.stop()

        # 3. Генерируем
        with st.spinner(f"🧠 Думаю ({quiz_lang})..."):
            try:
                Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
                
                # Промпт с учетом языка
                prompt = (
                    f"Проанализируй текст. Создай тест на языке: {quiz_lang}. "
                    f"Количество вопросов: {quiz_count}. "
                    f"Сложность: {quiz_difficulty}. "
                    "Верни JSON."
                )
                
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=Quiz,
                    prompt_template_str=prompt + " Текст: {text}",
                    llm=Settings.llm
                )
                
                result = program(text=text[:15000])
                st.session_state['quiz'] = result
            except Exception as e:
                st.error(f"Ошибка AI: {e}")
                st.stop()

# --- ВЫВОД РЕЗУЛЬТАТА ---
if 'quiz' in st.session_state:
    st.divider()
    for i, q in enumerate(st.session_state['quiz'].questions):
        st.subheader(f"{i+1}. {q.scenario}")
        st.radio("Варианты:", q.options, key=f"q{i}")
        with st.expander("Показать ответ"):
            st.write(f"Правильно: {q.options[q.correct_option_id]}")
            st.info(q.explanation)