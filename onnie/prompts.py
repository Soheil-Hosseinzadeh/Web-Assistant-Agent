"""Static texts used by the agent and by both interfaces."""

# Added to the agent's memory (as a plain user message) when the user presses stop.
STOP_TEXT = "User asks to stop right now"

# Used on the first message of every chat to generate a short sidebar title.
TITLE_PROMPT = """
I want you to take the user request and create a chat top in at most 6 words or less. The user request is provided in triple backticks: ```{user_request}```
Don't say anything extra, just output the chat topic.
"""

(
    ""
    "5 words or less: {user_request}, just answer the summary, don't say "
    "anything extra"
)

# Shown in the "About Onnie" pop-up (GUI) and by /info (CLI).
INFO_TEXT = """Hello there, dear friend! ✨ I'm Onnie, your delightful Search Assistant Agent ready to help you explore the wonderful world of information!

- I'm excellent at searching the web to find answers to your questions
- I can navigate websites with ease and gather information from multiple sources
- I'm skilled at taking screenshots to capture visual content when needed
- I love scrolling through pages to find what you're looking for
- I'm great at clicking links and exploring new destinations
- I can fill in forms and interact with webpages just like a human would

**I have been created by Soheil Hosseinzadeh: [linkedin page](https://www.linkedin.com/in/soheil-hosseinzadeh)**

Feel free to checkout my repo 😊: [github repository link](https://github.com/Soheil-Hosseinzadeh/Web-Assistant-Agent)"""
