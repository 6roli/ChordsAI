from tools import Tools
from LLMconfig import LLM 
from langgraph.graph import MessagesState, END, START, StateGraph
from langgraph.types import Command
from typing import Literal
from langchain_core.messages import SystemMessage


class PlayAgent:
    def __init__(self):
        self.tools = [Tools.play_note,Tools.play_chord]  # Add play_note function to tools list
        self.brain = LLM().get_llm_with_tools(self.tools)
        self.system_prompt = """You are a Musical Expert Agent. You can play notes and chords.
                                     Based on the note or chords you get from the user, you can play them.
                                     You should use either one of the following tools:
                                     1. play_note tool to play a note.
                                     2. play_chord tool to play a chord
                                    Only call a tool Once  ."""
        self.prompt=LLM().set_and_get_prompt(self.system_prompt)


    def node(self, state: MessagesState) -> Command[Literal['tools', END]]:
        """Play Agent node used to play Notes or Chords."""
        messages = state["messages"]
        response = self.brain.invoke(self.prompt.invoke({"messages":messages}))
        # response = self.chain.invoke(messages)
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



        play_agent = PlayAgent()
        tools=Tools()
        workflow=StateGraph(MessagesState)

        workflow.add_node("agent", play_agent.node)
        workflow.add_node("tools", tools.get_tool_node())

        workflow.add_edge(START, "agent")
        workflow.add_edge("tools", "agent")

        graph=workflow.compile()

        while True:
            user_input=input("User:")
            for event in graph.stream({"messages": [{"role": "user", "content": user_input}]},stream_mode="values"):
            # for event in graph.stream({"messages": [HumanMessage(user_input)]},stream_mode="values"):

                for messages in event['messages']:
                    if messages is type(AIMessage):
                        print(messages.content)
main()