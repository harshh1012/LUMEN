# src/rag_pipeline.py

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA


# ======================================
# LOAD VECTOR STORE
# ======================================

def load_vector_store(persist_dir="./vector_store", model_name="all-mpnet-base-v2"):
    embedding = HuggingFaceEmbeddings(model_name=model_name)
    db = Chroma(
        persist_directory=persist_dir,
        embedding_function=embedding
    )
    return db.as_retriever(search_kwargs={"k": 3})


# ======================================
# LOAD GROQ LLM
# ======================================

def load_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("❌ GROQ_API_KEY missing in .env file")

    return ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.3
    )


# ======================================
# BUILD RAG CHAIN (NO DOMAIN)
# ======================================

def build_rag_chain():
    retriever = load_vector_store()
    llm = load_llm()

    prompt_template = """
Use the following context to answer the question accurately and clearly.
If the answer is not available within the context, say:
"Information not found in the current database."

Context:
{context}

Question:
{question}

Answer:
"""

    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=prompt_template
    )

    chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )

    return chain


# ======================================
# RUN QUERY
# ======================================

def query_rag(question: str):
    rag_chain = build_rag_chain()

    # Only pass query now
    result = rag_chain.invoke({"query": question})

    print("\n🧠 Question:", question)
    print("\n💬 Answer:\n", result["result"])

    print("\n📎 Context Sources:")
    for doc in result["source_documents"]:
        print(f" - {doc.metadata.get('source')} | Chunk: {doc.metadata.get('chunk_id')}")


# ======================================
# MAIN
# ======================================

if __name__ == "__main__":
    question = input("💬 Enter your question: ")
    query_rag(question)
