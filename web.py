import streamlit as st
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

st.set_page_config(page_title="Colloid AI", page_icon=":rat:")
st.title(":rat: Корпоративный ИИ компании Colloid")

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
    Answer the user´s question using ONLY the provided context.
    Answer strictly in Russian language.

    Context:
    {context}
  
    Question:
    {question}
  
    Answer in Russian:"""
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
       
            chain = prompt | llm
            response = chain.invoke({"context": context_text, "question": user_query})

            st.markdown(response.content)
            st.feedback("thumbs", key=f"new_fb_{len(st.session_state.messages)}")

    st.session_state.messages.append({"role": "assistant", "content": response.content})
