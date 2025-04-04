This task is dedicated to the Anti-Corruption Directive within the government of Lower Franconia.

This includes, among other things, conducting a risk analysis for all areas of a given department. This risk analysis is updated every four years and proceeds as follows:

1.) Sending [Questionnaire No. 1](https://github.com/i-yam/hackathon/blob/main/challenge2/Fragebogen1.pdf) to the department heads (by email).

2.) The department heads complete Questionnaire No. 1 and return it (by email).

3.) A dedicated lawers files the completed Questionnaire No. 1 in the electronic file -> currently manually; successively as they are received.

4.) Checking whether all department heads have returned the questionnaires within the specified deadline. If not: Reminder and new deadline... -> then repeat No. 3 (possibly multiple loops)

5.) Evaluation of questionnaire No. 1 by a lawyer -> previously entered manually in Excel

6.) Creation of an overview with the results by a lawyer – in particular, categorizing the work areas according to different levels of corruption risk -> previously entered manually in Excel

7.) Differentiation:
a.) Work areas not at risk of corruption and work areas at risk of corruption -> A dedicated emplyee sends the department heads an information letter (via email); Risk analysis thus completed
b.) Work areas particularly vulnerable to corruption -> see further points

8.) Send [questionnaire no. 2](https://github.com/i-yam/hackathon/blob/main/challenge2/Fragebogen%20II%2C%20Blanco.pdf) to the employees (by email)

9.) Complete questionnaire no. 2 by the employees and return it (by email)

10.) File the completed questionnaire no. 2 in the electronic file ->  manually as they are received

11.) Check whether all employees have returned the questionnaires within the specified deadline; If not: Reminder and new deadline... -> then repeat No. 10 (possibly multiple loops)

12.) Evaluation of questionnaire No. 2 by a dedicated lawyer -> previously entered manually in [Excel](https://github.com/i-yam/hackathon/blob/main/challenge2/Auswertung%20Fragebogen%20II%3B%20fingiertes%20Ausfu%CC%88llbeispiel.xlsx)

13.) Sending a comprehensive letter to the department heads by email, explaining which Corruption Management requirements are not met according to the information provided (by the employees) in the questionnaires. The letter then outlines organizational and personnel improvement measures. -> Manual preparation of the individualized letters; the sample letter serves as a template (for each deficit addressed in the questionnaire, there is a sample note in this repository, which one has to manually copy from the sample letter into the individualized letter).

14.) Differentiation:
a.) Work areas particularly vulnerable to corruption -> risk analysis thus completed.
b.) Areas of work particularly at risk of systematic corruption (categorization will only be determined based on the survey in Questionnaire No. 2) -> see further points

15.) An organizational directive and accompanying handout will be sent with the letter to the department heads according to No. 11.

16.) Completion of the organizational directive by the department heads and return by email.

17.) A lawyer checks whether the organizational directives have been properly completed (in particular, they comply with the requirements of the Corruption Regulations).

18.) Differentiation:
a.) Organizational directive is properly completed -> filing of the organizational directive in the electronic file; manually by a lawyer.
b.) Organizational directive is not properly completed -> notification to the department head (by phone or email).

19.) Check whether all department heads have returned the organizational directives within the specified deadline. If not: Reminder and new deadline... -> then again 17 and 18 (possibly multiple loops)

In this repo you can finde questionaries No. 1 and No. 2 developed by the Ministry.

As you can see, there are many steps involved for many actors. Each step is not particularly extensive on its own, but the entire process takes a lot of time. 

Ideally, the solution is a small open-source program that all government employees have access to. Anyone who has something to do receives an automatically generated reminder email. 
