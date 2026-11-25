from smolagents import CodeAgent, tool, LiteLLMModel
import os
import tools
import yaml

with open("conf.yml", "r") as file:
    config = yaml.safe_load(file)


model = LiteLLMModel(
    model_id=config["MODEL"],
    api_base=config["BASE_URL"],
    api_key=config["API_KEY"],
    num_ctx=int(config["CONTEXT_LENGTH"]),
    temperature=0.1,
    flatten_messages_as_text=False,
)

# model = LiteLLMModel(
#     model_id=config["MODEL"],
#     api_base=config["BASE_URL"],
#     api_key=config["API_KEY"],
#     max_completion_tokens=int(config["CONTEXT_LENGTH"]),
#     temperature=0.1,
#     stream=True,
#     flatten_messages_as_text=False,
# )

# model = LiteLLMModel(
#     model_id="groq/qwen/qwen3.8-27b",
#     api_key=config["API_KEY"],
#     max_completion_tokens=int(config["CONTEXT_LENGTH"]),
#     temperature=0.1,
#     flatten_messages_as_text=False,
# )
os.environ["HTTP_PROXY"]="http://127.0.0.1:1080"
os.environ["HTTPS_PROXY"]="http://127.0.0.1:1080"

from smolagents import OpenAIServerModel
# model = OpenAIServerModel(
#     model_id="qwen/qwen3.8-27b",
#     api_base="https://api.groq.com/openai/v1",
#     api_key=config["API_KEY"],
#     temperature=0.1,
#     max_tokens=int(config["CONTEXT_LENGTH"]),
#     flatten_messages_as_text=False,
# )



# Create the agent
agent = CodeAgent(
    tools=[
        tools.start_browser,
        tools.stop_browser,
        tools.search_web,
        tools.open_page,
        tools.get_page_content,
        tools.click_element,
        # tools.mouse_move,
        # tools.mouse_click,
        # tools.mouse_double_click,
        tools.mouse_scroll,
        tools.keyboard_type,
        tools.keyboard_press,
        tools.take_screenshot,
    ],
    model=model,
    max_steps=config["MAX_STEP"],
    verbosity_level=2,
    instructions=config["INSTRUCTIONS"],
    step_callbacks=[tools.attach_requested_screenshots],
)

task = """Go to the ibm website, clear all the pop ups, then take a screeen shot of the bottom of the page."""
result = agent.run(task)