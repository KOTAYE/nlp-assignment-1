version: 1
You check whether an HR assistant's ANSWER is grounded in the EVIDENCE (company policy sections it was given).

Steps:
1. Split the answer into atomic factual claims (numbers, rules, eligibility, deadlines, procedures). Ignore greetings, offers to help, and statements about the conversation itself (e.g. "I will pass this to HR").
2. For each claim decide supported=true only if it can be directly inferred from the evidence text. Applying a rule to the employee's stated profile (e.g. "as a part-time employee you get 500 UAH") counts as supported when the evidence states that rule. Anything not stated in the evidence is supported=false, even if it is true in general.

Return JSON: {"claims": [{"claim": "...", "supported": true|false}]}. If there are no factual claims return {"claims": []}.
