import uuid
from sqlalchemy import or_
from os import getenv
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.prebuilt import ToolNode
from typing import TypedDict, Annotated
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models.transaction_model import Transaction
from ..models.user_model import User

load_dotenv()

open_router_api_key = getenv("OPEN_ROUTER_API_KEY")
if not open_router_api_key:
    raise ValueError("OPEN_ROUTER_API_KEY environment variable is not set")


# Step 1: Define a PROPER LangChain tool
@tool
def register_new_payment(
    amount: int,
    currency: str,
    payment_method: str,
    description: str = "",
    chat_id: str = "",
    phone_number: str = "",
    type: str = "expense",
):
    """Register a new payment transaction for a user."""

    db: Session = SessionLocal()
    user = (
        db.query(User)
        .filter(
            or_(
                User.services_authenticated["telegram"].astext == chat_id,
                User.services_authenticated["whatsapp"].astext == phone_number,
            )
        )
        .first()
    )
    if not user:
        return "User not found. Please register first with /auth."
    try:
        transaction = Transaction(
            user_id=user.id,
            value=amount,
            payment_method=payment_method,
            description=description,
            type=type,
            is_deleted=False,
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        return f"Transaction registered successfully: {transaction.id}"
    except Exception as e:
        db.rollback()
        return f"Failed to register transaction: {str(e)}"
    finally:
        db.close()


@tool
def auth_new_user(phone_number: str = "", chatId: str = ""):
    """Authenticate a new user and create a new account. If an phone_number is passed, it will be used to authenticate the user. Instead, if a chatId is passed, it will be used to authenticate the user. If the user already exists, return the existing user ID."""

    from sqlalchemy import or_

    db: Session = SessionLocal()
    try:
        # Check if user already exists
        existing_user = (
            db.query(User)
            .filter(
                or_(
                    User.services_authenticated["telegram"].astext == chatId,
                    User.services_authenticated["whatsapp"].astext == phone_number,
                )
            )
            .first()
        )
        if existing_user:
            return f"User already exists: {existing_user.id}"

        user = User(
            id=uuid.uuid4(),
            services_authenticated={"whatsapp": phone_number, "telegram": chatId},
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return f"User registered successfully: {user.id}"
    except Exception as e:
        db.rollback()
        return f"Failed to register user: {str(e)}"
    finally:
        db.close()


llm = ChatOpenAI(
    api_key=open_router_api_key,
    base_url="https://openrouter.ai/api/v1",
    model="openai/gpt-4o-mini",
    temperature=0.2,
)

llm_with_tools = llm.bind_tools([register_new_payment, auth_new_user])


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def tool_calling_llm(state: AgentState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}


tools = [register_new_payment, auth_new_user]
tool_node = ToolNode(tools)

builder = StateGraph(AgentState)

builder.add_node("agent", tool_calling_llm)
builder.add_node("tools", tool_node)

builder.add_edge(START, "agent")


# Conditional edge: check if tool was called
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END


builder.add_conditional_edges("agent", should_continue)
builder.add_edge("tools", "agent")  # After tool, go back to agent

graph = builder.compile()


# Step 6: Test
def start_graph_by_user_message(user_message: str):
    system_message = SystemMessage(
        content="You are a financial assistant. Extract the chat_id from the message (it will be in the format 'chat_id: <id>'). When users report payments or expenses, use the register_new_payment tool with the chat_id and other parameters: amount, currency, payment_method, description. Extract the information accurately from the user's message. Currency is usually BRL for Brazilian users. Payment method examples: PIX, credit card, etc. When received the /auth command, use the auth_new_user tool with the chat_id."
    )
    result = graph.invoke(
        {"messages": [system_message, HumanMessage(content=user_message)]}
    )
    print(result)
    return result["messages"][-1].content
