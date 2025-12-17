# Project Summary

## 1. What Went Well

### a. Team and Collaboration

The transition from an unstructured start to a clearly defined team structure was a key success factor in our team's performance.

* **Successful Role Assignment:** Smaragda proactively established the **Team Lead** role and successfully assigned specific responsibilities based on individual strengths, with Karl serving as the **Lead Developer**. This established a clear chain of command and technical direction.
* **High Team Spirit and Motivation:** The Team Lead served as the primary motivator, ensuring task engagement and maintaining high morale. Her persistent effort was crucial in driving team commitment, particularly in the initial phases, preventing potential stagnation.
* **Proactive Customer Communication:** Communication with the customer was consistently **great**. We maintained contact through four formal meetings and regular email exchanges, which facilitated prompt feedback and ensured our work remained aligned with the client's vision.
* **Effective Conflict Resolution:** Any conflicts or disagreements that arose were addressed immediately and constructively during scheduled virtual or face-to-face team meetings, ensuring that issues did not impede project progress.

### b. Project Development Process

The team adopted efficient practices that streamlined the flow from problem identification to solution implementation.

* **Clarity from Understanding:** Although initial motivation was low due to a lack of clear direction, it surged once the team fully grasped the core problem and the client’s vision. This strong conceptual clarity led to focused and productive development efforts.
* **Efficient Tooling and AI Integration:** The project utilized tools with simple and straightforward documentation. When unexpected technical hurdles occurred, the team effectively leveraged AI tools to quickly find solutions, drastically reducing the time spent troubleshooting and ensuring smooth continuity.

---

## 2. What Should Have Been Done Differently

### a. Team and Collaboration

While collaboration was generally strong, a few structural and motivational aspects could be refined for future projects.

* **Earlier Role Definition:** The initial period without clear responsibilities caused a motivational lag. In the future, **formal roles should be established during the very first project meeting** to prevent early uncertainty and accelerate task initiation.
* **Addressing Individual Contribution:** While the workload was generally distributed evenly based on expertise, there were variances in individual contribution levels. To ensure balanced accountability, **more rigorous, public check-ins on task progress** and regular peer feedback sessions should be implemented.
* **Proactive Customer Status Updates:** Although communication was good when questions arose, a more frequent, **scheduled proactive update** (e.g., a brief weekly status email even without immediate questions) could have provided the client with greater assurance of continuous progress.

### b. Project Development Process

We identified areas in the development process where specific technical decisions or scope management could have been executed differently.

* **Optimizing Core Logic Implementation:** The largest issues involved the initial configuration and connection between various services (Vercel, Notion) and developing the main application logic. **More focused effort should have been dedicated upfront to rapidly prototyping and stress-testing these core connections** to minimize initial friction.
* **Realistic Performance Optimization:** An attempt to enhance performance by implementing a relational database was made to replace JSON file reads for autofill. This was ultimately aborted because the computing limitations of the free-tier Vercel environment could not handle the necessary conversion in a reasonable time. **Future performance enhancements must be scoped within the constraints of the chosen infrastructure.**

---

## 3. What We Learnt

Our three-month experience provided valuable lessons spanning technical proficiency, process management, and team dynamics.

* **Acquired Technical Skills:** Karl learned significantly about **API integration and utilization**, gaining proficiency in incorporating external services into our own project architecture.
* **The 50/50 Rule of Development:** We learned that **coding represents only about 50% of a successful project's effort**. The remaining 50% is distributed across essential activities like **communication, effective use of Git, and thorough documentation** (e.g., refining use cases, managing user stories).
* **The Necessity of Process Regulation:** The early period of low activity proved that a **regulator or controller is essential** for development. We learned that the presence of an engaged Team Lead who actively monitors and manages the process is non-negotiable for success.
* **Time Management and Scope Regulation:** We learned that while initial estimates were generally accurate, **regulating the project's scope along the way** was vital to ensure a timely and complete delivery of core functionality.

---

## 4. Customer’s Opinion and Future Intentions

### Customer’s Plans

We believe that we will be in touch with the client and that they will continue to utilize the product after the course concludes.

### Future Intentions

The team has agreed to remain available to the client for minor maintenance and support, demonstrating our ongoing belief in the product's value. This includes tasks such as:

* Changing minor configuration variables.
* Addressing other simple tasks that do not require more than one hour per session.


## 5. Individual remarks

### Tuudur Jürgen Utt

My main role in this team ended up being QA. I wrote most of the automated tests for this project, conducted usability testing and set up a good portion of the CI pipeline. I also did significant work on requirements engineering. A more detailed account can be found under the contribution report section of the wiki. My main takeaways from this project are as follows:

- I should have been more proactive. Especially in the early parts on this project, when the team was disorganized, I should have stepped up to take charge of the chaos rather than wait for someone else to do so.
- Good documentation in really important. My main complaint is that it was really difficult to figure out what the development side was up to and what/why changes had been made. This forced me to play catch-up for the majority of the last three months. I am sure that my own lack of proper documenting has caused similar issue for others.
- Especially when working with new people, workflows and approach should really be established and agreed upon at the beginning of a project. People who are available at different times, are unclear on what they need to be doing, prioritize different things and work at drastically different paces (some are prototyping, while others try for more maintainable results) can make for a quite dysfunctional work environment.

I am a hypercritical person though - the project went well in most aspects and I sincerely hope everyone else involved largely shares that sentiment.


### Armin Liiv

My personal contribution to the project covered several different phases, including requirements work, feature development, user experience improvements, and manual testing.

At an early stage of the project, I contributed by defining and documenting a set of Non-Functional Requirements. These requirements were compiled into a dedicated wiki entry and helped clarify the overall expectations and constraints of the system from the beginning.

During development, I worked on extending the auto-fill functionality by integrating the Google Custom Search JSON API into the Vercel backend to populate missing company website URLs in the Notion CRM. Although the solution technically worked, it was only partially reliable in practice, as many companies lack an official website or cannot be identified due to naming differences or limited search visibility. These limitations were identified and documented during implementation.

I also implemented a user experience improvement that removed the previously used pop-up browser windows for auto-fill feedback. Successful operations now complete silently, while errors are displayed directly on the Notion page, resulting in a more seamless workflow for collaboration managers.

I also carried out manual acceptance testing by executing all defined use cases manually, documenting pass/fail results in the project wiki, and fixing distinct issues identified during this process.


### Karl Prink

### Requirements & Project Management
* Participated in client meetings to gather requirements and define the scope of the application.
* Assisted with general project management to ensure team alignment and task tracking.

### Design & Coding
* **Core Functionality:** Developed the main application logic and data flow.
* **API Integration:** Successfully integrated the Notion API to handle data synchronization.
* **Data Processing:** Implemented the data reading and conversion logic for *e-äriregister’s* JSON data files.
* **Database Architecture (Challenge):** Attempted to convert the data storage from JSON to a relational database. However, this implementation was evaluated and ultimately discarded due to the storage limitations of Vercel’s free hosting tier.

### Testing
* Wrote the first set of unit tests.
* Performed continuous iterative testing during the development of the main functionality to ensure stability.

### Documentation
* Wrote wiki and did some documentation

### Commits
![Commits](/docs/Commits.png)
