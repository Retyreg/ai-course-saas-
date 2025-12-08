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

# --- НАСТРОЙКИ ---
st.set_page_config(page_title="AI Course Factory", page_icon="🎓")
load_dotenv()

# --- СТРУКТУРА ДАННЫХ ---
class QuizQuestion(BaseModel):
    scenario: str = Field(..., description="Ситуация/Кейс")
    options: List[str] = Field(..., description="4 варианта ответа")
    correct_option_id: int = Field(..., description="Индекс правильного (0-3)")
    explanation: str = Field(..., description="Почему это верно")

class Quiz(BaseModel):
    questions: List[QuizQuestion]

# --- ИНТЕРФЕЙС ---
st.title("🎓 AI Course Generator")

# БЕЗОПАСНАЯ ПРОВЕРКА КЛЮЧЕЙ
# Мы проверяем наличие ключей на сервере, но НЕ отправляем их в браузер пользователя
has_llama = bool(os.getenv("LLAMA_CLOUD_API_KEY"))
has_openai = bool(os.getenv("OPENAI_API_KEY"))

if has_llama and has_openai:
    st.success("✅ API ключи загружены из безопасного хранилища (Streamlit Secrets).")
else:
    st.warning("⚠️ Ключи не найдены в настройках сервера. Введите их вручную для работы:")
    # Поля ввода показываем ТОЛЬКО если ключей нет на сервере. И они пустые.
    new_llama = st.text_input("LlamaCloud Key (llx-...)", type="password")
    new_openai = st.text_input("OpenAI Key (sk-...)", type="password")
    
    if new_llama and new_openai:
        os.environ["LLAMA_CLOUD_API_KEY"] = new_llama
        os.environ["OPENAI_API_KEY"] = new_openai
        st.rerun() # Перезагружаем страницу, чтобы применить

uploaded_file = st.file_uploader("Загрузи PDF инструкцию", type=["pdf"])

if uploaded_file:
    if st.button("🚀 Создать Тест"):
        
        # Проверка перед запуском
        if not os.environ.get("LLAMA_CLOUD_API_KEY"):
            st.error("❌ Нет LlamaCloud ключа! Введите его выше.")
            st.stop()
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        # --- ЭТАП 1: ПАРСИНГ ---
        with st.spinner("📄 Читаю документ через LlamaParse..."):
            try:
                parser = LlamaParse(
                    result_type="markdown", 
                    language="ru",
                    # Важно: если ключ не верный, библиотека иногда молчит, поэтому передаем явно
                    api_key=os.environ["LLAMA_CLOUD_API_KEY"] 
                )
                
                docs = SimpleDirectoryReader(
                    input_files=[tmp_path], 
                    file_extractor={".pdf": parser}
                ).load_data()
                
                # ЗАЩИТА ОТ ОШИБКИ IndexError
                if not docs:
                    st.error("❌ Ошибка: LlamaParse вернул пустой список.")
                    st.warning("Возможные причины:\n1. Неверный API ключ (проверьте, начинается ли он на 'llx-')\n2. Файл защищен паролем или пустой.")
                    st.stop()
                    
                text = docs[0].text
                st.info(f"Успешно прочитано {len(text)} символов.")
                
            except Exception as e:
                st.error(f"❌ Критическая ошибка парсинга: {e}")
                st.stop()

        # --- ЭТАП 2: ГЕНЕРАЦИЯ ---
        with st.spinner("🧠 Придумываю вопросы..."):
            try:
                Settings.llm = OpenAI(model="gpt-4o", temperature=0.1)
                
                program = LLMTextCompletionProgram.from_defaults(
                    output_cls=Quiz,
                    prompt_template_str="Создай 3 сложных ситуационных вопроса по тексту: {text}. Верни JSON.",
                    llm=Settings.llm
                )
                
                result = program(text=text[:5000])
                st.session_state['quiz'] = result
            except Exception as e:
                st.error(f"Ошибка при генерации вопросов (OpenAI): {e}")
                st.stop()

# --- ВЫВОД ---
if 'quiz' in st.session_state:
    st.success("✅ Тест готов!")
    for i, q in enumerate(st.session_state['quiz'].questions):
        st.markdown(f"---")
        st.subheader(f"Вопрос {i+1}")
        st.write(f"**Сценарий:** {q.scenario}")
        choice = st.radio("Ваш ответ:", q.options, key=i)
        
        if st.button(f"Проверить ответ {i+1}"):
            correct = q.options[q.correct_option_id]
            if choice == correct:
                st.success(f"Верно! {q.explanation}")
            else:
                st.error(f"Ошибка. Правильно: {correct}")
                # --- ЭКСПОРТ В HTML (НОВЫЙ БЛОК) ---
if 'quiz' in st.session_state:
    st.divider()
    st.subheader("📦 Экспорт курса")
    
    # Мы генерируем HTML-код с встроенным JavaScript для проверки ответов
    # Это "Single File Course" — работает везде без интернета
    
    quiz_json = st.session_state['quiz'].json()
    
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>AI Generated Course</title>
        <style>
            body {{ font-family: sans-serif; max_width: 800px; margin: 0 auto; padding: 20px; background: #f4f4f9; }}
            .card {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            h2 {{ color: #2c3e50; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; cursor: pointer; border-radius: 5px; }}
            .btn:hover {{ background: #0056b3; }}
            .feedback {{ margin-top: 10px; font-weight: bold; display: none; }}
            .correct {{ color: green; }}
            .wrong {{ color: red; }}
        </style>
    </head>
    <body>
        <h1>🎓 Экзамен по инструкции</h1>
        <div id="quiz-container"></div>

        <script>
            // Данные из Python вшиваются прямо сюда
            const quizData = {quiz_json};

            const container = document.getElementById('quiz-container');

            quizData.questions.forEach((q, index) => {{
                const card = document.createElement('div');
                card.className = 'card';
                
                let optionsHtml = '';
                q.options.forEach(opt => {{
                    optionsHtml += `<label style="display:block; margin: 5px 0;">
                        <input type="radio" name="q${{index}}" value="${{opt}}"> ${{opt}}
                    </label>`;
                }});

                card.innerHTML = `
                    <h3>Вопрос ${{index + 1}}</h3>
                    <p>${{q.scenario}}</p>
                    <form>${{optionsHtml}}</form>
                    <div class="btn" onclick="checkAnswer(${{index}}, this)">Проверить</div>
                    <div class="feedback" id="feedback-${{index}}"></div>
                `;
                container.appendChild(card);
            }});

            function checkAnswer(index, btn) {{
                const q = quizData.questions[index];
                const selected = document.querySelector(`input[name="q${{index}}"]:checked`);
                const feedbackEl = document.getElementById(`feedback-${{index}}`);
                
                if (!selected) {{
                    alert("Выберите вариант ответа!");
                    return;
                }}

                feedbackEl.style.display = 'block';
                const correctVal = q.options[q.correct_option_id];

                if (selected.value === correctVal) {{
                    feedbackEl.className = 'feedback correct';
                    feedbackEl.innerHTML = "✅ Верно! " + q.explanation;
                }} else {{
                    feedbackEl.className = 'feedback wrong';
                    feedbackEl.innerHTML = "❌ Ошибка. Правильный ответ: " + correctVal;
                }}
            }}
        </script>
    </body>
    </html>
    """

    # Кнопка скачивания
    st.download_button(
        label="📥 Скачать курс как HTML (для LMS)",
        data=html_template,
        file_name="course_package.html",
        mime="text/html"
    )