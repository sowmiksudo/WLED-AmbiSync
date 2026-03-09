import onnxruntime as ort
from huggingface_hub import hf_hub_download

def test():
    try:
        onnx_path = hf_hub_download(repo_id="Kalray/mobilenet-v2", filename="mobilenetv2.onnx")
        print(f"Downloaded OK: {onnx_path}")
        session = ort.InferenceSession(onnx_path)
        print("Inputs:", session.get_inputs()[0].name, session.get_inputs()[0].shape)
        print("Outputs:", session.get_outputs()[0].name, session.get_outputs()[0].shape)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
