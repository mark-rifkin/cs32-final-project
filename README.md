# CS 32 Final Project: Podium: a Jeopardy training app
<img src="assets/full_logo.png" width="400">

# FP Submission
## About 

## Setup
- Clone this repository
- Ensure miniconda or anaconda is installed 
- To install dependencies, run:
```
conda env create -f environment.yml
```

- To launch the app, run: 
```
conda activate podium 
python run.py
```
## How to play
Once the app loads, you can press start to get your first question. 

The app reads the question (or, as Jeopardy calls it, "Answer") aloud, and once it has finished reading, lights on the side of the clue indicate that you can buzz in. If you buzz too early, you are locked out for 250ms before you can buzz again. If you do not buzz within 5 seconds of buzzer unlock, the answer is revealed and you are marked incorrect. 

When you successfully buzz in, you have 5 seconds to answer (indicated by lights on the bottom of the screen). Answer aloud and press the answer button before time expires. 

Once you answer, the correct answer (or, as Jeopardy calls it, "Question") is revealed. Mark yourself right or wrong to move on to the next clue. You must answer in the form of a question (e.g. "What is...?")

Quit at any time by closing the window or pressing Quit in the menu. You can also view stats by pressing Stats in the menu. 


### Keyboard shortcuts
- ```Space``` to advance (start game, next question, answer) or buzz
- ```Enter``` to skip question
- ```<-``` to mark question incorrect,  ```->``` to mark question correct
- ```S``` to skip question
- ```M``` for menu


## Next steps:
*This project accomplished all of its original goals. In the future, I could implement:*
- Tutorial
- SFX settings: on/off/volume
- Filtering: filter questions by year, category, round, etc.(this would rely on repeated API calls and may be difficult depending on the specificity of the filter)
- Improved stats breakdowns, e.g. by category type
- Full game mode: (though this would be very difficult with the current random question API, and it's unclear that a better API exists)
- Local or online multiplayer
- Nicer graphic design (e.g. more skeuomorphic buttons w/ drop shadow)

## AI acknowledgment
ChatGPT used extensively with detailed requests for coding help/implementation, primarily: 
- Suggested some of the project architecture (ie models classes, services)
- Implemented upgrade from pyttsx3 to pygame in TTSservice
- Implemented data cleaning in get_random_question in QuestionService
- Implemented stats_store class
- Implemented GUI and GUI-based round controller (with very extensive guidance, iteration, and manual edits)
- Implemented SFX (again, with lots of iteration and manual edits)


# FP Status 
## Description
Console implementation of a simple Jeopardy training app ("Podium"). Retrieves questions from an online API, reads them aloud using Microsoft Edge's online text-to-speech service, simulates buzzer, and tracks statistics. 

## Requirements
Must run locally in Windows 11 (currently, the keypress logic is windows-only, but the GUI implementation might be cross-platform depending on whether I choose desktop or webapp)
Python package requirements: 
- requests
- edge-tts
- pygame-ce

Tested Python version 3.14.4 via miniconda

To run: open full project in VSCode and run src.main via Run and Debug menu, or use ```python -m src.main``` in a console.  

## Contributors
ChatGPT used extensively with detailed requests for coding help/implementation, primarily: 
- Suggested some of the project architecture (ie models classes, services)
- Implemented upgrade from pyttsx3 to pygame in TTSservice
- Implemented data cleaning in get_random_question in QuestionService
- Implemented stats_store class
- Implemented pre-caching of audio files in main.py and ttsservice
- Implemented multithreaded keyboard input and early-buzz lockout in round_control.py

# FP design
## Background
Jeopardy! is a popular American trivia game show. When the host finishes reading each question, a member of the production staff manually unlocks the buzzers to allow players to answer. Red lights on the edge of the question screen indicate that the players now can buzz. If players buzz before the buzzers are unlocked, they are locked out for a quarter of a second [source](https://www.jeopardy.com/jbuzz/behind-scenes/how-does-jeopardy-buzzer-work). Because multiple players often know the answer to a question, buzzer timing is a key part of what makes Jeopardy champions succesful. There are two main strategies: timing the buzz to the light and attempting to reduce reaction time, or timing the buzz to the host's voice [source](https://www.jeopardad.com/sample-page/jeopardy-prep/jeopardy-buzzing-strategy/).

However, there does not seem to be an online tool enabling Jeopardy practice with real-world buzzer conditions; that is, integrating both a computerized host reading the question and buzzer lights. The Wii Jeopardy game does essentially have this, although its question set is limited, it is somewhat slow, and it is not easily available. My goal is to create a tool for realistic Jeopardy practice that I can use to prepare if I ever get on the show (bucket list item!)

I am not sure at this point whether it would be better to create this as a desktop app, client-side webapp, or client-server webapp, and would appreciate feedback on this.

## Prioritized tasks
(May not get through all of these)
1. Question retreival.
There are several free APIs online which include jeopardy questions, this one seems like a reasonable one to use: https://jeopardy.drun.sh/.

(Lower priority) Ideally I would be able to scrape the entire [J-archive](https://j-archive.com/) in order to play complete games with coherent categories rather than single questions, but there does not appear to be a simple way to do so in Python. There is the R package [whatr](https://rdrr.io/github/kiernann/whatr/f/README.md), I have some R experience and wonder if there is a way to call this package from Python -- to explore.

2. Out-loud question reading
Read the retrieved question out-loud using a text-to-speech package. [pyttsx3](https://pypi.org/project/pyttsx3/) is one example.

3. Buzzer integration
Allow the player to buzz in at the end of the text-to-speech question, and indicate unlock with red lights. (I am not sure how difficult it will be to figure out when the question ends)

4. Stats tracking
Track buzzer speed, correct/incorrect answers (potentially integrating semantic answer checking, but it's simpler to just show the correct answer and have the player indicate correct/incorrect), full game scoring. Potentially allow player to create an account to save and track stats over time.


