from tools import Tools
from LLMconfig import LLM 
from langgraph.graph import MessagesState, END, START, StateGraph
from langgraph.types import Command
from typing import Literal
from langchain_core.messages import SystemMessage

class searchAgent:

    def __init__(self):
        t=Tools()
        self.tools=[t.search_tool]
        self.brain = LLM().get_llm_with_tools(self.tools)
        self.system_prompt = """You are a Musical Expert Agent. 
        Based on the song input you should use the tool to search in the internet the chords for used in the orignal song."""
        self.prompt=LLM().set_and_get_prompt(self.system_prompt)

    def node(self, state: MessagesState) -> Command[Literal['tools',END]]:
        """Search agent node used to search up chords for songs"""
        messages=state["messages"]
        response=self.brain.invoke(self.prompt.invoke({"messages":messages}))
        if len(response.tool_calls) > 0:
            next_node = "tools"
        else:
            next_node = END
        return Command(goto=next_node, update={"messages": [response]})
    
from playAgent import PlayAgent
from langgraph.graph import MessagesState, END, START, StateGraph
from langchain_core.messages import HumanMessage, AIMessage
from tools import Tools

def main():
    if __name__ == "__main__":
        song_agent=searchAgent()

        tools=Tools()
        workflow=StateGraph(MessagesState)

        workflow.add_node("agent", song_agent.node)
        workflow.add_node("tools", tools.get_tool_node())

        workflow.add_edge(START, "agent")
        workflow.add_edge("tools", "agent")
        graph=workflow.compile()

        while True:
            user_input=input("User:")
            for event in graph.stream({"messages": [{"role": "user", "content": user_input}]},stream_mode="values"):
            # for event in graph.stream({"messages": [HumanMessage(user_input)]},stream_mode="values"):

                for messages in event['messages']:
                    if type(messages) is AIMessage:
                        print(messages.content)
main()