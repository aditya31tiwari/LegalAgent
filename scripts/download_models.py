"""
Script to download and verify candidate embedding and legal models:
1. bhavyagiri/InLegal-Sbert (IIT KGP Indian legal domain SBERT)
2. BAAI/bge-small-en-v1.5 (High performance general embedding)
3. law-ai/InLegalBERT (IIT KGP base Indian legal model)
"""
import sys

def download_sbert(model_name: str):
    print(f"\n[+] Loading SentenceTransformer model: {model_name}...")
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        embedding = model.encode("This agreement is governed by the laws of India under Section 27 of the Indian Contract Act.")
        print(f"    ✓ Successfully loaded {model_name}! Embedding shape: {embedding.shape}")
        return True
    except Exception as e:
        print(f"    ✗ Failed to load {model_name}: {e}")
        return False

def download_transformers(model_name: str):
    print(f"\n[+] Loading AutoModel/Tokenizer: {model_name}...")
    try:
        from transformers import AutoTokenizer, AutoModel
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        inputs = tokenizer("Section 74 of the Indian Contract Act provides for reasonable compensation.", return_tensors="pt")
        outputs = model(**inputs)
        print(f"    ✓ Successfully loaded {model_name}! Output tensor shape: {outputs.last_hidden_state.shape}")
        return True
    except Exception as e:
        print(f"    ✗ Failed to load {model_name}: {e}")
        return False

if __name__ == "__main__":
    print("=== Downloading & Verifying Models for LegalAgent ===")
    
    # 1. bhavyagiri/InLegal-Sbert (Siamese network for sentence embeddings)
    s1 = download_sbert("bhavyagiri/InLegal-Sbert")
    
    # 2. BAAI/bge-small-en-v1.5 (Fast lightweight baseline)
    s2 = download_sbert("BAAI/bge-small-en-v1.5")
    
    # 3. law-ai/InLegalBERT (Base transformer)
    s3 = download_transformers("law-ai/InLegalBERT")
    
    print("\n=== Summary ===")
    print(f"bhavyagiri/InLegal-Sbert : {'READY' if s1 else 'FAILED'}")
    print(f"BAAI/bge-small-en-v1.5   : {'READY' if s2 else 'FAILED'}")
    print(f"law-ai/InLegalBERT       : {'READY' if s3 else 'FAILED'}")

