import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper

st.set_page_config(page_title="Colloid AI", page_icon=":rat:")
st.title(":rat: Корпоративный ИИ компании Colloid")

use_internet = st.sidebar.toggle("🌍 Искать в интернете", value=False)

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
    
    llm = ChatGroq(
        temperature=0.3,
        model_name="llama-3.3-70b-versatile",
        groq_api_key=st.secrets["GROQ_API_KEY"]
    )

    template = """You are a helpful corporate assistant for "Colloid".
    1. Answer the user´s question using the provided context.
    2. CRITICAL: Identify the language of the user's Question. You MUST output your final Answer entirely in that EXACT SAME language.
    3. If the provided Context is in a different language than the user's Question, TRANSLATE the facts from the Context into the user's language before answering.
    4. If the user asks to translate a text or asks a general question, fulfill their request using your general knowledge.

    Context:
    {context}
  
    Question:
    {question}
  
    Answer:"""
    prompt = PromptTemplate.from_template(template)
   
    return vectorstore.as_retriever(), llm, prompt

retriever, llm, prompt = init_rag()

if "messages" not in st.session_state:
    st.session_state.messages = []

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"]=="assistant":
            st.feedback("thumbs", key=f"history_fb_{i}")
if user_query := st.chat_input("Спроси что-нибудь про компанию..."):

    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.messages.append({"role": "user", "content": user_query})

    with st.chat_message("assistant"):
        with st.spinner("Ищу в документах..."):
            relevant_docs = retriever.invoke(user_query)
            context_text = "\n".join([doc.page_content for doc in relevant_docs])

      if use_internet:
            with st.spinner("Ищу в Википедии... 📚"):
                try:
                    search = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
                    web_results = search.run(user_query)
                    context_text += f"\n\nФакты из интернета:\n{web_results}"
                except Exception:
                    pass
        
        chain = prompt | llm
            def stream_generator():
                for chunk in chain.stream({"context": context_text, "question": user_query}):
                    yield chunk.content

            full_response = st.write_stream(stream_generator())
            
            st.feedback("thumbs", key=f"new_fb_{len(st.session_state.messages)}")

    st.session_state.messages.append({"role": "assistant", "content": full_response})
