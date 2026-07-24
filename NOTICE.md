# Research inspiration and attribution

kchat's compact plan–link–query and single-correction workflow was informed by ideas described in the following paper:

> Aleksandr Perevalov and Andreas Both. “Text-to-SPARQL Goes Beyond English: Multilingual Question Answering Over Knowledge Graphs through Human-Inspired Reasoning.” In *Proceedings of the First International TEXT2SPARQL Challenge co-located with Text2KG at ESWC 2025*, CEUR Workshop Proceedings, vol. 4094, pp. 77–93, 2025. https://ceur-ws.org/Vol-4094/paper6.pdf. doi:[10.48550/arXiv.2507.16971](https://doi.org/10.48550/arXiv.2507.16971).

The paper presents mKGQAgent and motivated kchat's use of explicit planning guidance, entity/relation linking, multilingual semantic paraphrasing, and bounded execution feedback. kchat implements a smaller, independent adaptation suited to its existing two-tool architecture. It does not include or depend on the mKGQAgent software, its experience-pool implementation, or its source code.

The mKGQAgent software and its citation metadata are available at <https://github.com/WSE-research/text2sparql-agent>.
