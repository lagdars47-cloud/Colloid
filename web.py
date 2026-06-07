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

st.set_page_config(page_title="Colloid AI", page_icon=":rat:")
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
    
    llm_vision = ChatGroq(
        temperature=0.1,
        model_name="llama-3.2-90b-vision-preview",
        groq_api_key=st.secrets["GROQ_API_KEY"]
    )

    llm_text = ChatGroq(
        temperature=0.5,
        model_name="llama-3.3-70b-versatile",
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
        system_rules = f"""You are a helpful corporate assistant for "Colloid".
        1. Answer the user's question using the provided context.
        2. CRITICAL: Identify the language of the user's Question. You MUST output your final Answer entirely in that EXACT SAME language.
        3. YOU ARE A MULTIMODAL VISION AI. You CAN see images perfectly. Analyze the attached image carefully and fulfill the user's request. NEVER say you cannot see images.
        4. Reaction to insults: If a user insults someone or calls them by an animal name, the AI must respond with a witty, ironic, and friendly retort, implying the user is describing themselves.
           - VARIETY: Never repeat the same phrase twice. Use different styles: sarcastic, playful, philosophical, or witty.
           - TONE: Maintain a friendly, "teacher-like" or "sassy friend" persona.

        [HISTORY]
        {history_to_use}

        [CONTEXT]
        {context_to_use}
        """
        combined_text = f"{system_rules}\n\n[USER QUESTION]\n{query_to_use}"

        combined_text = combined_text[:4000]
        
        messages = [
            HumanMessage(
                content=[
                    {"type": "text", "text": combined_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": base64_image},
                    },
                ]
            )
        ]
        
        for chunk in llm_vision.stream(messages):
            yield chunk.content
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
                        if img.mode !='RGB':
                            img - img.convert('RGB')
                        img.thumbnail((800,800))
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=85)
                        base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        image_b64 = f"data:image/jpeg;base64,{base64_str}"
                        context_text += f"\n[User attached an image: {f.name}]\n"
                    except Exception as e:
                        st.error(f"Ошибка при обработке картинки: {e}")
                    
                elif f.name.endswith(".txt"):
                    context_text += f"\nСодержимое файла {f.name}:\n{f.getvalue().decode('utf-8')}\n"
                elif f.name.endswith(".pdf"):
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
