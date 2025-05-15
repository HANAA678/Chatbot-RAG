from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings  
from langchain_community.vectorstores import FAISS  
from langchain_community.document_loaders import DirectoryLoader, TextLoader 
import os

loader = DirectoryLoader("documents", glob="*.txt", loader_cls=TextLoader)
documents = loader.load()

text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)

embeddings = OpenAIEmbeddings()  

db = FAISS.from_documents(chunks, embeddings)

db.save_local("vectorstore_index")

print("✅ Index créé et sauvegardé dans 'vectorstore_index'")

