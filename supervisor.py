
from searchAgent import searchAgent
from playAgent import PlayAgent
from tools import Tools
from LLMconfig import LLM 
from langgraph.graph import MessagesState, END, START, StateGraph
from langgraph.types import Command
from typing import Literal
from langchain_core.messages import SystemMessage


class supervisorAgent():
    def __init__(self):
        self.tools=[searchAgent.node,PlayAgent.node]
        self.brain=LLM().get_llm_with_tools(self.tools)
        self.prompt=LLM().set_and_get_prompt(""" Based on the user's input you have to decide what tool to use:
                                             1.searchAgent: used to look up the chords for a song
                                             2.playAgent used to play notes and chords.
                                             If you do not need to use any tool reply to the user as best as you can.""")

    def node(self,state:MessagesState)->Command[Literal['tools',END]]:
        messages=state['messages']
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
        song_agent=supervisorAgent()

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