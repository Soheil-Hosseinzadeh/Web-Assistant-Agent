import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from smolagents import CodeAgent, tool, LiteLLMModel
import tools
import yaml
import litellm

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

os.environ["HTTP_PROXY"] = "http://127.0.0.1:1080"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1080"

# from smolagents import OpenAIServerModel
# model = OpenAIServerModel(
#     model_id="qwen/qwen3.8-27b",
#     api_base="https://api.groq.com/openai/v1",
#     api_key=config["API_KEY"],
#     temperature=0.1,
#     max_tokens=int(config["CONTEXT_LENGTH"]),
#     flatten_messages_as_text=False,
# )


# def manage_context(memory_step, agent: CodeAgent):
#     """
#     Automatically removes the oldest 50% of agent memory
#     when context usage reaches the configured threshold.
#     """

#     MAX_CONTEXT = int(config["CONTEXT_LENGTH"])
#     CONTEXT_THRESHOLD = 0.90
#     KEEP_RATIO = 0.70

#     # Reconstruct the actual messages sent to the model.
#     messages = agent.write_memory_to_messages()

#     # Convert smolagents ChatMessages to LiteLLM-compatible messages.
#     formatted_messages = [
#         {
#             "role": getattr(msg.role, "value", msg.role),
#             "content": msg.content,
#         }
#         for msg in messages
#     ]

#     # Count tokens, with a character-based fallback.
#     try:
#         token_count = litellm.token_counter(
#             model=agent.model.model_id,
#             messages=formatted_messages,
#         )
#     except Exception:
#         token_count = sum(
#             len(str(msg["content"])) for msg in formatted_messages
#         ) // 3

#     threshold = int(MAX_CONTEXT * CONTEXT_THRESHOLD)

#     print(
#         f"\n[Memory] {token_count:,}/{MAX_CONTEXT:,} tokens "
#         f"({token_count / MAX_CONTEXT:.1%})"
#     )

#     if token_count >= threshold:

#         steps = agent.memory.steps
#         old_count = len(steps)

#         remove_count = int(old_count * (1 - KEEP_RATIO))

#         if remove_count > 0:
#             agent.memory.steps = steps[remove_count:]

#         print(
#             f"[Memory] Context limit approaching! "
#             f"Removed {remove_count} old steps. "
#             f"Remaining: {len(agent.memory.steps)} steps."
#         )

CONTEXT_THRESHOLD = 0.90
def manage_context(memory_step, agent):

    MAX_CONTEXT = int(config["CONTEXT_LENGTH"])
    global CONTEXT_THRESHOLD

    # Get token usage from the latest completed step.
    usage = getattr(memory_step, "token_usage", None)

    if usage is None:
        return

    # This is the input size of the latest model request,
    # NOT the cumulative input tokens across all requests.
    current_tokens = usage.input_tokens

    print(
        f"\n[Memory] {current_tokens:,}/{MAX_CONTEXT:,} tokens "
        f"({current_tokens / MAX_CONTEXT:.1%})"
    )

    if current_tokens >= MAX_CONTEXT * CONTEXT_THRESHOLD:

        steps = agent.memory.steps

        # Keep the latest half of memory.
        keep_count = max(1, len(steps) // 2)
        agent.memory.steps = steps[-keep_count:]

        print(f"[Memory] Pruned old history. " f"Kept {keep_count}/{len(steps)} steps.")


# Create the agent
agent = CodeAgent(
    tools=[
        tools.start_browser,
        tools.stop_browser,
        tools.search_web,
        tools.open_page,
        tools.get_page_text_content,
        tools.get_page_raw_content,
        tools.click_element,
        tools.mouse_scroll,
        tools.keyboard_type,
        tools.keyboard_press,
        tools.fill_input,
        tools.take_screenshot,
        # -----------------------------------------------------------------------------
        # Uncomment These three below tools in the case You are using a strong qualified VLM
        # that can correctly determine the coordinate of an element in the page.
        # -----------------------------------------------------------------------------
        # tools.mouse_move,
        # tools.mouse_click,
        # tools.mouse_double_click,
    ],
    model=model,
    max_steps=config["MAX_STEP"],
    verbosity_level=2,
    instructions=config["INSTRUCTIONS"],
    step_callbacks=[tools.attach_requested_screenshots, manage_context],
    executor_kwargs={"timeout_seconds": 120},
    additional_authorized_imports=[
        "requests",
        "bs4",
        "PIL",
        "PIL.Image",
        "json",
        "datetime",
        "re",
        "numpy",
        "pandas",
        "urllib",
        "httpx",
        "io",
    ],
)

while True:
    try:
        task = input("\nYou: ")

        if task.lower() in ("exit", "quit"):
            break

        result = agent.run(
            task,
            reset=False,
        )

        print(f"\nAgent: {result}")

    except KeyboardInterrupt:
        print("\nExiting...")
        break

    except Exception as e:
        print(f"\nError: {e}")
