import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun
import PyPDF2
import base64
from langchain_core.messages import HumanMessage, SystemMessage
import io
from PIL import Image
from langchain_google_genai import ChatGoogleGenerativeAI, HarmCategory, HarmBlockThreshold
import streamlit as st
import requests
import uuid

if  "user_db" not in st.session_state:
    st.session_state.user_db = {"admin@colloid.com": "123456"}

if "is_logged_in" not in st.session_state:
    st.session_state.is_logged_in = False

if not st.session_state.is_logged_in:
    st.title("🔒 Вход в Colloid")
    st.info("Пожалуйста, войдите или зарегистрируйтесь.")

    with st.container(border=True):
        tab_login, tab_reg = st.tabs(["🔑 Вход", "📝 Регистрация"])

        with tab_login:
            with st.form("login_form"):
                log_email = st.text_input("Ваш Email")
                log_password = st.text_input("Пароль", type="password")
                submit_login = st.form_submit_button("Войти", type="primary", use_container_width=True)

                if submit_login:
                    if log_email in st.session_state.user_db and st.session_state.user_db[log_email] == log_password:
                        send_telegram_notification("Пользователь", log_email, "Успешный вход")
                        st.session_state.is_logged_in = True
                        st.rerun()
                    else:
                         st.error("Неверный Email или пароль. Возможно, вы не зарегистрированы?")
                                 
        with tab_reg:
            with st.form("reg_form"):
                reg_name = st.text_input("Как вас зовут?")
                reg_email = st.text_input("Email")
                reg_password = st.text_input("Придумайте пароль", type="password")
                submit_reg = st.form_submit_button("Зарегистрироваться", type="primary", use_container_width=True)

                if submit_reg:
                    if reg_email in st.session_state.user_db:
                        st.warning("Этот Email уже зарегистрирован! Перейдите на вкладку (Вход).")
                    elif reg_name and reg_emeil and reg_password:
                        st.session_state.user_db[reg_email] = reg_password
                        send_telegram_notification(reg_name, reg_email, "Новая регистрация")
                        st.success("Успешно! Теперь перейдите на вкладку (Вход) и введите свои данные.")
                    else:
                        st.error("Пожалуйста, заполните все поля.")
        
def init_analytics_and_cookies():
    GA_ID = "G-KZPZR173W4"
    API_SECRET = "RNpQHhUDR_aicfXGe-GA1w" 
    
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    
        try:
            url = f"https://www.google-analytics.com/mp/collect?measurement_id={GA_ID}&api_secret={API_SECRET}"
            payload = {
                "client_id": st.session_state.user_id,
                "events": [{
                    "name": "page_view",
                    "params": {
                        "page_title": "Colloid AI",
                        "session_id": st.session_state.user_id
                    }
                }]
            }
            requests.post(url, json=payload, timeout=2)
        except Exception:
            pass
            
    if "cookies_accepted" not in st.session_state:
        st.session_state.cookies_accepted = False

    if not st.session_state.cookies_accepted:
        col1, col2 = st.columns([4, 1], vertical_alignment="center")
        with col1:
            st.info("🍪 **Colloid использует файлы cookie** для сбора аналитики. Нажимая «Принять», вы соглашаетесь с правилами GDPR.")
        with col2:
            if st.button("Принять", type="primary", use_container_width=True):
                st.session_state.cookies_accepted = True
                st.rerun()

init_analytics_and_cookies()
st.title(":rat: Colloid Chat")
uploaded_file = st.sidebar.file_uploader("📎 Загрузить документ", type=["txt", "pdf"])
extracted_text = ""

if uploaded_file is not None:
    if uploaded_file.name.endswith(".txt"):
        extracted_text = uploaded_file.read().decode("utf-8")
    elif uploaded_file.name.endswith(".pdf"):
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        for page in pdf_reader.pages:
            extracted_text += page.extract_text() + "\n"
    st.sidebar.success(f"файл {uploaded_file.name} прочитан!")

@st.cache_resource
def init_rag():
    loader = TextLoader("company_rules.txt", encoding="utf-8")
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
    splits = text_splitter.split_documents(docs)

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    )
    
    llm_vision = ChatGoogleGenerativeAI(
        temperature=0.1,
        model="gemini-2.5-flash",  # <--- Актуальная модель!
        google_api_key=st.secrets["GOOGLE_API_KEY"],
        safety_settings={
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        }
    )
    
    llm_text = ChatGroq(
        temperature=0.5,
        model="llama-3.3-70b-versatile",
        groq_api_key=st.secrets["GROQ_API_KEY"]
    )

    template = """You are a helpful corporate assistant for "Colloid".
    1. Answer the user's question using the provided context.
    2. CRITICAL: Identify the language of the user's Question. You MUST output your final Answer entirely in that EXACT SAME language.
    3. If the provided Context is in a different language than the user's Question, TRANSLATE the facts from the Context into the user's language before answering.
    4. If the user asks to translate a text, tell a joke, or asks a general question, fulfill their request using your general knowledge and the internet context. Feel free to be natural and conversational.
    5. If the user asks to analyze an image, extract text, fix errors, or answer questions from it, fulfill their request accurately using your vision capabilities and internet context.
    6. Reaction to insults: If a user insults someone or calls them by an animal name, the AI must respond with a witty, ironic, and friendly retort, implying the user is describing themselves.
       - VARIETY: Never repeat the same phrase twice. Use different styles: sarcastic, playful, philosophical, or witty.
       - TONE: Maintain a friendly, "teacher-like" or "sassy friend" persona. 
       - EXAMPLES OF VARIETY: 
         * "I see you've brought a mirror into this conversation."
         * "That's a bold way to introduce yourself!"
         * "I think you might be talking about your own reflection."
         * "Interesting choice of words—I suspect you know more about that than I do."
         * "Your descriptive skills are quite… self-reflective today!"
    
    История нашей предыдущей переписки:
    {chat_history}

    Context:
    {context}
    
    Question:
    {question}
    
    Answer:"""
    prompt = PromptTemplate.from_template(template)
    
    return vectorstore.as_retriever(), llm_text, llm_vision, prompt

retriever, llm_text, llm_vision, prompt = init_rag()

if "messages" not in st.session_state:
    st.session_state.messages = []

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            st.feedback("thumbs", key=f"history_fb_{i}")

chain = prompt | llm_text

def stream_generator(context_to_use, query_to_use, history_to_use, base64_image=None):
    if base64_image:
        from langchain_core.messages import HumanMessage

        combined_text = f"""You are a helpful corporate assistant for "Colloid".
        [RULES]
        1. Answer the user's question using the provided context.
        2. Always respond in the user's language.
        3. Reaction to insults: If a user insults someone or calls the, by an animal name, respond with a witty, ironic, and friendly report, implying the user is describing themselves.

        [HISTORY] {history_to_use}
        [CONTEXT] {context_to_use}

        [USER QUESTION]
        Analyze this image and answer: {query_to_use}"""

        clean_b64 = base64_image.split(",")[1] if "," in base64_image else base64_image

        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": f"Analyze this image and answer: {query_to_use}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{clean_b64}"}},
                ]
            )
        ]

        try:
            for chunk in llm_vision.stream(messages):
                yield chunk.content
        except Exception as e:
            yield f"❌ **Ошибка Google API:** {str(e)}"
            
    else:
        for chunk in chain.stream({"context": context_to_use, "question": query_to_use, "chat_history": history_to_use}):
            yield chunk.content

history_text = ""
for msg in st.session_state.messages[:-1][-6:]:
    role = "Пользователь" if msg["role"] == "user" else "Ассистент"
    history_text += f"{role}: {msg['content']}\n"

if not history_text:
    history_text = "Это начало нашего диалога, истории пока нет."

if prompt_data := st.chat_input("Спроси что-нибудь...", accept_file="multiple"):
    user_query = prompt_data.text
    attached_files = prompt_data.files
    
    if not user_query:
        user_query = "Посмотри прикрепленные файлы и расскажи, что в них."
    
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    with st.chat_message("user"):
        st.markdown(user_query)
        if attached_files:
            for f in attached_files:
                st.caption(f"Прикреплен файл: {f.name}")

    with st.chat_message("assistant"):
        context_text = "Facts from Colloid:\n"
        image_b64 = None
        
        if attached_files:
            for f in attached_files:
                ext = f.name.lower()
                if ext.endswith((".png", ".jpg", ".jpeg")):
                    try:
                        image_bytes = f.getvalue()
                        img = Image.open(io.BytesIO(image_bytes))
                        
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                            
                        img.thumbnail((800, 800))
                        
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=85)
                        base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        
                        image_b64 = f"data:image/jpeg;base64,{base64_str}"
                        context_text += f"\n[User attached an image: {f.name}]\n"
                    except Exception as e:
                        st.error(f"Ошибка при обработке картинки: {e}")
                elif ext.endswith(".txt"):
                    context_text += f"\nСодержимое файла {f.name}:\n{f.getvalue().decode('utf-8')}\n"
                elif ext.endswith(".pdf"):
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page in pdf_reader.pages:
                        context_text += page.extract_text() + "\n"

        with st.spinner("Думаю и ищу информацию... 🔍"):
            try:
                relevant_docs = retriever.invoke(user_query)
                context_text += "\n".join([doc.page_content for doc in relevant_docs])
            except Exception:
                pass
            
            try:
                search = DuckDuckGoSearchRun()
                web_results = search.run(user_query)
                context_text += f"\n\nFacts from the internet:\n{web_results}"
            except Exception:
                pass

        full_response = st.write_stream(stream_generator(context_text, user_query, history_text, image_b64))
        
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.feedback("thumbs", key=f"new_fb_{len(st.session_state.messages)}")
