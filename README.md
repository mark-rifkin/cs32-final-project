# CS 32 Final Project: Jeopardy
## Background
Jeopardy! is a popular American trivia game show. When the host finishes reading each question, a member of the production staff manually unlocks the buzzers to allow players to answer. Red lights on the edge of the question screen indicate that the players now can buzz. If players buzz before the buzzers are unlocked, they are locked out for a quarter of a second. Because multiple players often know the answer to a question, buzzer timing is a key part of what makes Jeopardy! champions succesful.[buzzer system source](https://www.jeopardy.com/jbuzz/behind-scenes/how-does-jeopardy-buzzer-work). Successful champions will often 

However, there does not seem to be an online tool

## Prioritized tasks
1. Question retreival.
There are several free APIs online which include jeopardy questions, this one seems like a reasonable one to use: https://jeopardy.drun.sh/.

(Lower priority) Ideally I would be able to scrape the entire [J-archive](https://j-archive.com/) in order to play complete games with coherent categories rather than single questions, but there does not appear to be a simple way to do so in Python. There is the R package [whatr](https://rdrr.io/github/kiernann/whatr/f/README.md), I have some R experience and wonder if there is a way to call this package from Python -- to explore.

2. Out-loud question reading
Read the retrieved question out-loud using a text-to

3. Buzzer integration
