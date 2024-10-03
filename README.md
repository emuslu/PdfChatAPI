# PdfChatAPI
Start by creating a .env file in the root directory.  
GEMINI_API_KEY (mandatory), DATABASE_URL (not mandatory)  
GEMINI_API_KEY = your_gemini_api_key  
Install all required dependencies with pip install -r requirements.txt  
Now you are ready to start the app by python main.py  
From a REST API Client like postman or thunderclient, send a post request to localhost:8000/v1/pdf with form-data body. Body should only have a file key with your pdf file as value. Only pdf files are accepted.  
After sending a request you should get a pdf_id. With that pdf_id, send a request to localhost:8000/v1/chat/{pdf_id} with a json body like {"message": "What is the main topic of the document I provided?"}.  
Finally you can see your response.
