from transformers import AutoTokenizer, AutoModelForCausalLM
from litellm import completion

import os

class HfLocalBackend:
    def __init__(self, model_name, device="auto", max_gpu_memory=None, hostname=None):
        self.model_name = model_name
        self.device = device
        self.max_gpu_memory = max_gpu_memory
        self.hostname = hostname

        # If a hostname is given, then this HF instance is hosted as a web server.
        # Therefore, do not start the AIOS-based HF instance.
        if self.hostname is not None:
            return
        
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=device,
            max_memory=self.max_gpu_memory,
            use_auth_token=os.environ["HUGGING_FACE_API_KEY"],
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            device_map=device,
            use_auth_token=os.environ["HUGGING_FACE_API_KEY"]
        )
        self.tokenizer.chat_template = "{% for message in messages %}{% if message['role'] == 'user' %}{{ ' ' }}{% endif %}{{ message['content'] }}{% if not loop.last %}{{ ' ' }}{% endif %}{% endfor %}{{ eos_token }}"

    def inference_online(self, messages, temperature, stream=False):
        return str(completion(
            model="huggingface/" + self.model_name,
            messages=messages,
            temperature=temperature,
            api_base=self.hostname,
        ))
    
    def __call__(
        self,
        messages,
        temperature,
        stream=False,
    ):
        if self.hostname is not None:
            return self.inference_online(messages, temperature, stream=stream)
        
        if stream:
            raise NotImplemented

        inputs = self.tokenizer.apply_chat_template(messages,
                                                       tokenize=True,
                                                       add_generation_prompt=True,
                                                       return_dict=True,
                                                       return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        temperature = temperature if temperature > 0.5 else 0.5
        response  = self.model.generate(**inputs,
                                        temperature=temperature,
                                        max_length=4096,
                                        top_k=10,
                                        num_beams=4,
                                        early_stopping=True,
                                        do_sample=True,
                                        num_return_sequences=1,
                                        eos_token_id=self.tokenizer.eos_token_id)
        length    = inputs["input_ids"].shape[1]
        result    = self.tokenizer.decode(response[0][length:])

        return result

class VLLMLocalBackend:
    def __init__(self, model_name, device="auto", max_gpu_memory=None, hostname=None):
        self.model_name = model_name
        self.device = device
        self.max_gpu_memory = max_gpu_memory
        self.hostname = hostname

        # If a hostname is given, then this vLLM instance is hosted as a web server.
        # Therefore, do not start the AIOS-based vLLM instance.
        if self.hostname is not None:
            return

        try:
            import vllm

            self.model = vllm.LLM(
                model_name,
                tensor_parallel_size=1 if max_gpu_memory is None else len(max_gpu_memory)
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        except ImportError:
            raise ImportError("Could not import vllm Python package"
                              "Please install it with `pip install python`")
        except Exception as err:
            print("Error loading vllm model:", err)

    def inference_online(self, messages, temperatures, stream=False):
        return str(completion(
            model="hosted_vllm/" + self.model_name,
            messages=messages,
            temperature=temperature,
            api_base=self.hostname,
        ))

    def __call__(
        self,
        messages,
        temperature,
        stream=False,
    ):
        if self.hostname is not None:
            return self.inference_online(messages, temperature, stream=stream)
        
        assert vllm
        if stream:
            raise NotImplemented

        parameters = vllm.SamplingParams(temperature=temperature)
        prompt     = self.tokenizer.apply_chat_template(messages,
                                                        tokenize=False)
        response   = self.model.generate(prompt, parameters)
        result     = response[0].outputs[0].text

        return result
