1. **Understanding the problem**
   “I read the problem statement, but I’m not fully clear on what they expect in the final output. Can you explain it in simple terms and tell me what I should focus on first?”

2. **Planning the project**
   “I was thinking of splitting this into smaller parts instead of doing everything at once. Does that make sense? What would be a reasonable order to work on them?”

3. **Database design**
   “For the transaction data, I’m thinking of keeping stores, products and transactions separate. Is there any issue with this approach, especially when handling returns?”

4. **Generating sample data**
   “I don’t have the actual dataset yet. Can I generate some sample retail transactions to test the importer? I want the data to include normal sales, returns and a few invalid cases.give a prompt to generate the script for geenrating the data and let me review it and decide”

5. **Making assumptions**
   “I’m assuming a return should refer to an earlier sale from the same store and for the same product. Should I also check whether the total returned quantity exceeds the original quantity?”


6. **Import validation**
   “Suppose a CSV has some valid rows and some invalid ones. Would it be better to import the valid rows and show errors for the others, or reject the whole file?”

7. **Understanding an error**
   “I’m getting a different result from what I expected when I run the tests. Can you help me understand what might be causing it before suggesting a fix?”

8. **API design**
   “For uploading a large CSV, I was thinking of processing it in the background instead of making the user wait for the entire import. Is that worth doing for this project?”

10. **Dashboard decisions**
    “For the dashboard, I think the user should be able to filter transactions by date and store. What other information would actually be useful instead of adding charts just for the sake of it?”

11. **Frontend and backend**
    “The frontend and backend are running separately. Can you explain how I should configure the API URL so that it works locally and after deployment?”

12. **Testing edge cases**
    “I want to test more than just a correct CSV. Which edge cases should I check for things like missing columns, invalid quantities, duplicate IDs and returns?”

13. **CI failures**
    “My GitHub Actions check is failing even though the code runs on my machine, help me understand the error and whether it’s a code issue or a formatting/configuration problem?”

14. **Deployment doubts**
    “I’m trying to deploy the frontend and backend separately, but I’m confused about which environment variables belong in each place. Can you explain what each one should point to?”

15. **Reviewing the final result**
    “Can you help me check whether the current implementation covers the important requirements from the problem statement? I want to identify anything I might have missed before submitting it.”
