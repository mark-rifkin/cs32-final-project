# CS 32 Final Project: Jeopardy
## Background
Jeopardy! is a popular American trivia game show. When the host finishes reading each question, a member of the production staff manually unlocks the buzzers to allow players to answer. Red lights on the edge of the question screen indicate that the players now can buzz. If players buzz before the buzzers are unlocked, they are locked out for a quarter of a second [source](https://www.jeopardy.com/jbuzz/behind-scenes/how-does-jeopardy-buzzer-work). Because multiple players often know the answer to a question, buzzer timing is a key part of what makes Jeopardy champions succesful. There are two main strategies: timing the buzz to the light and attempting to reduce reaction time, or timing the buzz to the host's voice [source](https://www.jeopardad.com/sample-page/jeopardy-prep/jeopardy-buzzing-strategy/).

However, there does not seem to be an online tool enabling Jeopardy practice with real-world buzzer conditions; that is, integrating both a computerized host reading the question and buzzer lights. The Wii Jeopardy game does essentially have this, although its question set is limited, it is somewhat slow, and it is not easily available. My goal is to create a tool for realistic Jeopardy practice that I can use to prepare if I ever get on the show (bucket list item!)

I am not sure at this point whether it would be better to create this as a desktop app, client-side webapp, or client-server webapp, and would appreciate feedback on this.

## Prioritized tasks
1. Question retreival.
There are several free APIs online which include jeopardy questions, this one seems like a reasonable one to use: https://jeopardy.drun.sh/.

(Lower priority) Ideally I would be able to scrape the entire [J-archive](https://j-archive.com/) in order to play complete games with coherent categories rather than single questions, but there does not appear to be a simple way to do so in Python. There is the R package [whatr](https://rdrr.io/github/kiernann/whatr/f/README.md), I have some R experience and wonder if there is a way to call this package from Python -- to explore.

2. Out-loud question reading
Read the retrieved question out-loud using a text-to

3. Buzzer integration
