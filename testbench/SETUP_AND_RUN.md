# Testing of Tracking feature
In camera 2, ingest demo2.mp4 and go to the "Tracker" tab and wait for processing
Once processed finish, and threat is detected, there will be a glow on camera 2
to simulate the suspect has been detected by camera 2


# Testing of local LLM 
Turn off your wifi to simulate poor connectivity and run the app as usual 
Ensure:
1. Ollama installed and running on localhost:11434
2. Pulled the ollama model by running
```bash
ollama pull qwen3-vl:4b
``` 


The app should run fine as there is a fallback to Ollama vision model 