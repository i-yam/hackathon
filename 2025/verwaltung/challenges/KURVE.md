KURVE - KI-unterstützte Recherche und Verarbeitung von Stellungnahmen und Erstellung von Ergebnisdokumenten.

The digitalization of public administration is an important task for accelerating processes for the benefit of the public and for conducting efficient, reliable evaluations. A frequently occurring issue, for which automated evaluation is still in its infancy, is the processing of large volumes of non-formally structured statements. Public authorities are regularly confronted with the fact that many statements (in extreme cases, 5,000-100,000) are submitted during participation procedures, and all of these must be individually reviewed (currently by hand). It should be noted that many content-related aspects of the statements are not relevant to the procedure, as they were already addressed in the preparation phase of the procedure, or comments relate to later steps of specific issues (e.g., details of project implementation).

The challenges and tasks are therefore:

1. Automatically reading texts from, for example, PDFs, which can contain both OCR-enabled and handwritten text, as well as images, etc. – the sky's the limit here.
2. All statements must then be reviewed for content and summarized for key content concerns. It must be ensured that all submitted aspects have been considered, but redundant or repetitive content is removed. Since it can also be assumed that the authors of the statements use AI as a tool, a mere "remove duplicates" tool is no longer sufficient. The clusters would therefore be detected using similarity metrics, etc.
3. The result should provide a clustered summary of all statements based on various criteria:
    — Content/technical concerns (e.g., the arguments presented regarding forests, water, etc.)
    — When designating specific areas, also based on the content of the individual areas. ("...The following points were raised regarding Area 1")
    — If necessary, additional aspects, special examples, or individual concerns that do not fit with the other aspects should be reliably recorded.
4. At the same time, internal traceability from the result containing the summarized content to the individual statement would be desirable.
5. Reliable anonymization of the content to protect personal data within the statements is desirable in order to minimize manual steps and, if necessary, to arrive close to a publishable final result.
6. Finally, the result should be usable as a "consideration document." This is a document in which the various concerns of the statements are grouped according to content and no longer inserted as individual statements, allowing a regional planning assessment to be made for each group. There are many examples of this online in the area of ​​public participation processes in Bavaria. In this folder you can find a hypothetical [example](https://github.com/i-yam/hackathon/blob/main/challenge1/16%20Beispielstellung%20-%20Hackathon_Datenschutzkonform%20Ri.pdf).

The task in this step ultimately consists of assigning appropriate response texts to the arguments clustered according to step 3, which then address several aspects of the same topic. It would be desirable to create a suitable template that prepares the document and perhaps also suggests AI-generated standard responses, which would then only ultimately have to be revised manually.

7. And, of course, important: Data protection must be guaranteed throughout the entire process. If this applies, the use of AI, along with other automated steps, is expressly desired.

In the past, all of these steps were processed individually. Perhaps you can make a valuable contribution to digitizing our administration here, within the framework of the new possibilities offered by AI and automation. Of course, it is fundamentally desirable to solve all of the challenges mentioned above, but even partial solutions or solutions to individual task steps could make a valuable contribution.
