import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

class LLM:
    
    def __init__(self):
        load_dotenv()
        # self.llm = ChatGroq(groq_api_key=os.getenv("GROQ_API_KEY"), model="llama-3.3-70b-versatile")
        self.llm = ChatGroq(groq_api_key=os.getenv("GROQ_API_KEY"), model="qwen-qwq-32b")

        self.prompt=None

    def get_llm(self):
        return self.llm
    
    def set_and_get_prompt(self,system_prompt):
        self.prompt=ChatPromptTemplate(
            [
                ("system", system_prompt),
                MessagesPlaceholder("messages")

            ]
        )
        return self.prompt
        
    def get_llm_with_tools(self, tools):
        return self.llm.bind_tools(tools)