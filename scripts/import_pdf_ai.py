
import openai
import pdfminer
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams
import nltk
nltk.download('punkt')
from nltk.tokenize import word_tokenize
import os
from dotenv import load_dotenv
import argparse

# Load the environment variables from the .env file
load_dotenv()

# Replace with your own OpenAI API key or set the OPENAI_API_KEY environment variable
openai.api_key =  os.getenv('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')

def count_tokens(text):
    """Counts the number of tokens in a string.
    Args:
        text (str): The text to count the tokens of.
    Returns:
        int: The number of tokens.
    """

    # This is not a perfect way to count tokens for ChatGPT, but it's good enough for our purposes.
    tokens = word_tokenize(text)
    return len(tokens)

def break_up_file(tokens, chunk_size, overlap_size):
    """Breaks up a file into chunks of tokens.
    Args:
        tokens (list): A list of tokens.
        chunk_size (int): The number of tokens in each chunk.
        overlap_size (int): The number of tokens to overlap between chunks.
    Returns:
        list: A list of lists of tokens.
    """

    if len(tokens) <= chunk_size:
        yield tokens
    else:
        chunk = tokens[:chunk_size]
        yield chunk
        yield from break_up_file(tokens[chunk_size-overlap_size:], chunk_size, overlap_size)

def break_up_file_to_chunks(text, chunk_size=2000, overlap_size=0):
    """Breaks up a file into chunks of tokens.
    Args:
        text (str): The text to break up.
        chunk_size (int): The number of tokens in each chunk.
        overlap_size (int): The number of tokens to overlap between chunks.
    Returns:
        list: A list of lists of tokens.
    """

    tokens = word_tokenize(text)
    return list(break_up_file(tokens, chunk_size, overlap_size))

def convert_to_detokenized_text(tokenized_text):
    """Converts a list of tokens to a detokenized string.
    Args:
        tokenized_text (list): A list of tokens.
        Returns:
        str: A detokenized string.
        """
    
    prompt_text = " ".join(tokenized_text)
    prompt_text = prompt_text.replace(" 's", "'s")
    return prompt_text

def call_chatGPT(prompt, max_tokens = 1000, temperature=0.2):
    """Calls the OpenAI API to generate text.
    Args:
        prompt (str): The prompt to use for the API call.
        max_tokens (int): The maximum number of tokens to generate.
        temperature (float): The temperature to use for the API call.
    Returns:
        str: The generated text.
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        n=1,
        stop=None,
        temperature=temperature,
    )
    return response.choices[0].message.content

def summarize_text_into_chunks(text):
    """Summarizes a text into chunks.
    Args:
        text (str): The text to summarize. 
    Returns:
        str: The summarized text.
        int: The number of chunks.
    """

    all_summaries = []
    list_chunk = break_up_file_to_chunks(text)

    for i, chunk in enumerate(list_chunk):
        local_text = convert_to_detokenized_text(chunk)


        # We take 100 characters from the previous paragraph
        prompt = "Write a long summary for a technical expert\
                of the following paragraph, from a paper, refering to the text as -This publication-:\n" \
                + local_text

        result = call_chatGPT(prompt)

        all_summaries.append(result)

    concatenated_summaries = "\n".join(all_summaries)
    nb_chunks = len(list_chunk)
    return concatenated_summaries, nb_chunks

if __name__ == "__main__":
    script_path = os.path.dirname(os.path.realpath(__file__))

    parser = argparse.ArgumentParser()
    parser.add_argument('--path_pdf', 
                        help='Path to a pdf file', 
                        type=str, 
                        default=os.path.join(script_path, '../example/2020.12.15.422967v4.full.pdf'))
    parser.add_argument('--save_summary', 
                        help='Save the summary in a txt file along the pdf file', 
                        type=bool, 
                        default=False)
    
    parser.add_argument('--cut_bibliography',
                        help='Try not to summarize the bibliography at the end of the pdf file',
                        type=bool,
                        default=True)
   
    parser.add_argument('--chunk_length',
                        help='This is to increase the final length of the summary. The document is summarized in chunks. More \
                        chunks means a longer summary. Inconsitencty across the sections could occur with larger number. Typically \
                        1 is a good value for an abstract and 2, 3 for more details.',
                        type=int,
                        default=1)
    
    args = parser.parse_args()

    pdf_path = args.path_pdf
    save_summary = args.save_summary
    chunk_length = args.chunk_length

    # Extract text from the PDF
    laparams = LAParams()
    text = extract_text(pdf_path, laparams=laparams)

    # We remove the bibliography
    # This is a very low tech way to do it, we will improve it later
    if args.cut_bibliography:
        if "References" in text:
            text = text.split("References")[0]
        if "Bibliography" in text:
            text = text.split("Bibliography")[0]

    # We summarize the text into chunks
    nb_chunks = 10

    current_text = text
    while (nb_chunks > chunk_length):        
        current_text, nb_chunks = summarize_text_into_chunks(current_text)
        print(f"Current number of chunks:{nb_chunks}")
    
    # We can afford to clean up if the text is not too long
    if ((nb_chunks > 1) & (count_tokens(current_text) < 2000)):
        print("Cleaning up the summary")
        # We count the number of tokens
        # If it small enough, we send the text for a last clean up. 
        prompt = "Can you clean up this publication summary to remove redundant information? Make \
            sure to keep the final text with the same amount of details:\n" \
                + current_text

        current_text = call_chatGPT(prompt, max_tokens = 2000)

    # We save the summary in a txt file
    if save_summary:
        summary_path = pdf_path.replace(".pdf", ".txt")
        with open(summary_path, "w") as f:
            f.write(current_text)

    # We print the final summary
    print(current_text)
