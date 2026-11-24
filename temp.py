
import os
import base64
import litellm
import yaml

with open("conf.yml", "r") as file:
    config = yaml.safe_load(file)

def encode_image(image_path: str) -> str:
    """Load a JPG image and encode it as Base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


image_path = "./images/12.jpg"
base64_image = encode_image(image_path)

response = litellm.completion(
    model=config["MODEL"],
    api_base=config["BASE_URL"],
    api_key=config["API_KEY"],
    temperature=0.1,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What is the coordination of the X close button of the pop up in the image?"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        }
    ]
)

print(response.choices[0].message.content)
