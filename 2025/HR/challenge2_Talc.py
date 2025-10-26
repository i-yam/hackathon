import requests

import textwrap

import os



# ----------------------------

# 📌 Company & context information

# ----------------------------



ORG_CONTEXT = """
You are an internal conflict reflection assistant at JOPP GmbH.
📖 COMPANY BACKGROUND:
JOPP was founded in 1919 as Theodor Jopp KG, originally producing bicycle parts and agricultural accessories. 
Since 1991, the company has been owned by the Büchs family. 
JOPP has grown steadily through acquisitions, product development, and international expansion.
Today, JOPP has around 1,600 employees worldwide and a turnover of approximately €200 million. 
It operates in Europe, Asia, and America, serving the automotive and industrial sectors.
🏢 ORGANIZATIONAL STRUCTURE:
- CEO: Anna Schmidt
- HR Director: Markus Weber (reports to CEO)
- Head of Engineering: Laura Keller (reports to CEO)
- Engineering Team Lead: Tom Bauer (reports to Head of Engineering)
- Product Team Lead: Sarah Li (reports to CEO)
- Employees: Max Meier, Julia Roth, Ahmed Khan, etc.
📌 Reporting:
- Max Meier → Engineering Team Lead (Tom Bauer)
- Julia Roth → Product Team Lead (Sarah Li)
- Ahmed Khan → Engineering Team Lead (Tom Bauer)
You are talking to one of these employees. Your job is to help them reflect on a workplace conflict in a neutral, empathetic, and systemic way.
You do NOT make legal, medical, or HR decisions. You help them clarify their perception, resources, and potential next steps.
"""



EMPLOYEES = ["Max Meier", "Julia Roth", "Ahmed Khan"]

CONTACT_LIST = [

    "HR Director: Markus Weber",

    "Team Lead: Tom Bauer or Sarah Li",

    "Trusted Person",

    "Works Council",

    "External Mediation (upon request)"

]



SAVE_FILE = "last_conflict_chat.txt"



# ----------------------------

# 🧠 LLM Call

# ----------------------------



def call_llm(prompt):

    response = requests.post(

        "http://localhost:11434/api/generate",

        json={"model": "llama3", "prompt": prompt, "stream": False},

        timeout=300

    )

    return response.json().get("response", "").strip()



# ----------------------------

# 🧍 User Selection

# ----------------------------



def select_employee():

    print("\n👤 Please select who you are:")

    for idx, emp in enumerate(EMPLOYEES, start=1):

        print(f"  {idx}. {emp}")

    choice = input("Enter number: ").strip()

    if choice.isdigit() and 1 <= int(choice) <= len(EMPLOYEES):

        return EMPLOYEES[int(choice)-1]

    else:

        print("Invalid choice. Defaulting to 'Max Meier'.")

        return "Max Meier"



# ----------------------------

# 📜 Ask initial reflection questions

# ----------------------------



def ask_initial_questions():

    answers = []

    questions = [

        "Can you briefly describe the situation that is currently concerning you?",

        "When did this situation first occur?",

        "Who is involved?",

        "How does this situation make you feel?",

        "What would be different if this situation no longer weighed on you?",

    ]

    print("\n🧭 Let's start with a few reflection questions.")

    for q in questions:

        ans = input(f"{q}\n📝 Your answer: ").strip()

        answers.append((q, ans))

    return answers



# ----------------------------

# 🪞 Generate initial summary

# ----------------------------



def generate_summary(conflict_input, all_answers, employee):

    answer_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in all_answers])

    prompt = textwrap.dedent(f"""
    {ORG_CONTEXT}
    The employee speaking is: {employee}
    Initial conflict description:
    {conflict_input}
    Reflection answers:
    {answer_text}
    Please provide a structured, empathetic summary including:
    - Factual and emotional key aspects of the conflict
    - Possible patterns or dynamics at play
    - Constructive next steps (without making decisions)
    - Mention relevant internal contact points if appropriate (HR, team lead, works council)
    Keep the tone neutral, supportive, and professional.
    """)

    return call_llm(prompt)



# ----------------------------

# 💬 Infinite chat loop with LLM

# ----------------------------



def continue_chat(chat_history):

    print("\n💬 You can now continue the conversation with the assistant. Type 'exit' to finish.\n")

    while True:

        user_input = input("🧍 You: ").strip()

        if user_input.lower() in ["exit", "quit"]:

            break



        chat_history.append(f"You: {user_input}")

        prompt = ORG_CONTEXT + "\n\n" + "\n".join(chat_history) + "\nAssistant:"

        response = call_llm(prompt)

        print(f"🤖 Assistant: {response}\n")

        chat_history.append(f"Assistant: {response}")



# ----------------------------

# 💾 Save and load chat history

# ----------------------------



def save_chat(chat_history):

    with open(SAVE_FILE, "w", encoding="utf-8") as f:

        f.write("\n".join(chat_history))

    print(f"💾 Chat saved to {SAVE_FILE}")



def load_chat():

    if os.path.exists(SAVE_FILE):

        with open(SAVE_FILE, "r", encoding="utf-8") as f:

            history = f.read().splitlines()

        print(f"✅ Loaded previous chat from {SAVE_FILE}")

        return history

    else:

        print("⚠️ No previous chat found.")

        return []



# ----------------------------

# 🚀 Main

# ----------------------------



def main():

    print("🤝 Welcome to the JOPP Conflict Reflection Assistant.")

    print("You can talk here in a safe, non-judgmental space.\n")



    # Check if previous chat exists

    if os.path.exists(SAVE_FILE):

        resume = input("🕓 Do you want to resume your last conversation? (yes/no): ").lower()

        if resume.startswith("y"):

            chat_history = load_chat()

            continue_chat(chat_history)

            save_chat(chat_history)

            return



    # New conversation

    employee = select_employee()

    conflict_input = input("\n🔷 Please describe the situation you're concerned about:\n📝 ").strip()

    if not conflict_input:

        print("❌ The conflict description must not be empty.")

        return



    answers = ask_initial_questions()



    summarize = input("\n🪞 Would you like a summary and possible next steps? (yes/no): ").lower()

    chat_history = []

    if summarize.startswith("y"):

        summary = generate_summary(conflict_input, answers, employee)

        print("\n✅ Summary & Reflection:")

        print("---------------------------------")

        print(summary)

        chat_history.append(f"Assistant: {summary}")



        print("\n📌 If you want to take next steps, these internal contact points are available:")

        for c in CONTACT_LIST:

            print(f" - {c}")



    # Start the infinite chat loop

    continue_chat(chat_history)



    # Save chat

    save_chat(chat_history)

    print("\n🙏 Thank you for sharing your thoughts. Goodbye.")



if __name__ == "__main__":

    main()
Footer
