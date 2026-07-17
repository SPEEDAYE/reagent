# src/util/doc_template/BusinessRequirement/Initial_template.py — BR template factory.
#
# Outline:
#   Create_BR_Initial_Template(authors) → BusinessRequirement
#     Returns 3-chapter BR:
#       1. Business requirements (7 subchapters: Background, Opportunity,
#          Objectives, Success metrics, Vision, Risks, Assumptions/deps)
#       2. Scope and limitations (4 subchapters)
#       3. Business context (3 subchapters)
#   Create_Business_Requirements(BR, chapter)  populates chapter 1
#   Create_Scope_Requirements(BR, chapter)     populates chapter 2
#   Create_Business_Context(BR, chapter)       populates chapter 3
from util.doc_template.BusinessRequirement.BR import BusinessRequirement
from util.doc_template.chapter import CHAPTER


def Create_BR_Initial_Template(authors: str) -> BusinessRequirement:
    title = "Software Requirement Specification"
    introduction = 'This document outlines the software requirements for the project.'
    BR =  BusinessRequirement(title, introduction, authors)
    chapters_1 = CHAPTER(
        SECTION = '1',
        title="Business requirements",
        introduction="""Projects are launched in the belief that creating or changing a product will provide worthwhile
benefits for someone and a suitable return on investment. The business requirements describe
the primary benefits that the new system will provide to its sponsors, buyers, and users. Business
requirements directly influence which user requirements to implement and in what sequence."""
    )
    Create_Business_Requirements(BR, chapters_1)
    chapters_2 = CHAPTER(
        SECTION = '2',
        title="Scope and limitations",
        introduction="This section describes what the reaction will and will not do. You need to state both what the solution being developed is and what it is not."
    )
    Create_Scope_Requirements(BR, chapters_2)
    chapters_3 = CHAPTER(
        SECTION = '3',
        title="Business context", # 可变章节
        introduction="This section enumerates context information of business requirements."
    )
    Create_Business_Context(BR, chapters_3)
    return BR

def Create_Business_Context(BR: BusinessRequirement, chapter: CHAPTER):
    bc_3_1 = CHAPTER(
        SECTION = '3.1',
    title = "Stakeholder profiles",
    introduction = """Stakeholders are the people, groups, or organizations that are actively involved in a project, are
affected by its outcome, or are able to influence its outcome (Smith 2000; IIBA 2009; PMI 2013).
The stakeholder profiles describe different categories of customers and other key stakeholders
for the project. You needn’t describe every stakeholder group, such as legal staff who must check
for compliance with pertinent laws on a website development project. Focus on different types
of customers, target market segments, and the various user classes within those segments. Each
stakeholder profile should include the following information:
- The major value or benefit that the stakeholder will receive from the product. Stakeholder
value could be defined in terms of:
• Improved productivity.
• Reduced rework and waste.
• Cost savings.
• Streamlined business processes.
• Automation of previously manual tasks.
• Ability to perform entirely new tasks.
• Compliance with pertinent standards or regulations.
• Improved usability compared to current products.
- Their likely attitudes toward the product.
- Major features and characteristics of interest.
- Any known constraints that must be accommodated.
"""
    )
    bc_3_2 = CHAPTER(
        SECTION = '3.2',
    title = "Project priorities",
    introduction = """To enable effective decision making, the stakeholders must agree on the project’s priorities. One
way to approach this is to consider the five dimensions of features, quality, schedule, cost, and staff
(Wiegers 1996). Each dimension fits in one of the following three categories on any given project:
- Constraint: A limiting factor within which the project manager must operate
- Driver: A significant success objective with limited flexibility for adjustment
- Degree of freedom: A factor that the project manager has some latitude to adjust and balance against the other dimensions
"""
    )
    bc_3_3 = CHAPTER(
        SECTION = '3.3',
    title = "Deployment considerations",
    introduction = """Summarize the information and activities that are needed to ensure an effective deployment of the
solution into its operating environment. Describe the access that users will require to use the system,
such as whether the users are distributed over multiple time zones or located close to each other.
State when the users in various locations need to access the system. If infrastructure changes are
needed to support the software’s need for capacity, network access, data storage, or data migration,
describe those changes. Record any information that will be needed by people who will be preparing
training or modifying business processes in conjunction with deployment of the new solution."""
    )
    
    BR.add_subchapter(chapter)
    chapter.add_subchapter(bc_3_1)
    chapter.add_subchapter(bc_3_2)
    chapter.add_subchapter(bc_3_3)

def Create_Scope_Requirements(BR: BusinessRequirement, chapter: CHAPTER):
    sr_2_1 = CHAPTER(
        SECTION = '2.1',
    title = "Major features",
    introduction = """List the product’s major features or user capabilities, emphasizing those that distinguish it from
previous or competing products. Think about how users will use the features, to ensure that the list is
complete and that it does not include unnecessary features that sound interesting but don’t provide
customer value. Give each feature a unique and persistent label to permit tracing it to other system
elements. You might include a feature tree diagram, as described later in this chapter."""
    )
    sr_2_2 = CHAPTER(
        SECTION = '2.2',
    title = "Scope of initial release",
    introduction = """Summarize the capabilities that are planned for inclusion in the initial product release. Scope is often
defined in terms of features, but you can also define scope in terms of user stories, use cases, use case
flows, or external events. Also describe the quality characteristics that will let the product provide
the intended benefits to its various user classes. To focus the development effort and maintain
a reasonable project schedule, avoid the temptation to include every feature that any potential
customer might eventually want in release 1.0. Bloatware and slipped schedules are common
outcomes of such insidious scope stuffing. Focus on those features that will provide the most value, at
the most acceptable cost, to the broadest community, in the earliest time frame."""
    )
    sr_2_3 = CHAPTER(
        SECTION = '2.3',
    title = "Scope of subsequent releases",
    introduction = """If you envision a staged evolution of the product, or if you are following an iterative or incremental
life cycle, build a release roadmap that indicates which functionality chunks will be deferred and
the desired timing of later releases."""
    )
    sr_2_4 = CHAPTER(
        SECTION = '2.4',
    title = "Limitations and exclusions",
    introduction = """List any product capabilities or characteristics that a stakeholder might expect but that are not
planned for inclusion in the product or in a specific release. List items that were cut from scope, so the
scope decision is not forgotten. Maybe a user requested that she be able to access the system from
her phone while away from her desk, but this was deemed to be out of scope. State that explicitly in
this section: “The new system will not provide mobile platform support."""
    )
    
    BR.add_subchapter(chapter)
    chapter.add_subchapter(sr_2_1)
    chapter.add_subchapter(sr_2_2)
    chapter.add_subchapter(sr_2_3)
    chapter.add_subchapter(sr_2_4)

def Create_Business_Requirements(BR: BusinessRequirement, chapter: CHAPTER):
    br_1_1 = CHAPTER(
        SECTION = '1.1',
    title = "Background",
    introduction = """Summarize the rationale and context for the new product or for changes to be made to an existing
one. Describe the history or situation that led to the decision to build this product."""
    )
    br_1_2 = CHAPTER(
        SECTION = '1.2',
    title = "Business opportunity",
    introduction = """For a corporate information system, describe the business problem that is being solved or the process
being improved, as well as the environment in which the system will be used. For a commercial
product, describe the business opportunity that exists and the market in which the product will be
competing. This section could include a comparative evaluation of existing products, indicating
why the proposed product is attractive and the advantages it provides. Describe the problems that
cannot currently be solved without the envisioned solution. Show how it aligns with market trends,
technology evolution, or corporate strategic directions. List any other technologies, processes, or
resources required to provide a complete customer solution."""
    )
    br_1_3 = CHAPTER(
        SECTION = '1.3',
    title = "Business objectives",
    introduction = """Summarize the important business benefits the product will provide in a quantitative and measurable
way. Platitudes (“become recognized as a world-class <whatever>”) and vaguely stated improvements
(“provide a more rewarding customer experience”) are neither helpful nor verifiable. """
    )
    br_1_4 = CHAPTER(
        SECTION = '1.4',
    title = "Success metrics",
    introduction = """Specify the indicators that stakeholders will use to define and measure success on this project. Identify the factors that have the greatest impact on achieving that success, including 
factors both within and outside the organization’s control."""
    )
    br_1_5 = CHAPTER(
        SECTION = '1.5',
    title = "Vision statement",
    introduction = """Write a concise vision statement that summarizes the long-term purpose and intent of the product.
The vision statement should reflect a balanced view that will satisfy the expectations of diverse
stakeholders. It can be somewhat idealistic but should be grounded in the realities of existing or
anticipated markets, enterprise architectures, corporate strategic directions, and resource limitations.
The following keyword template works well for crafting a product vision statement (Moore 2002):
- For [target customer]
- Who [statement of the need or opportunity]
- The [product name]
- Is [product category]
- That [major capabilities, key benefit, compelling reason to buy or use]
- Unlike [primary competitive alternative, current system, current business process]
- Our product [statement of primary differentiation and advantages of new product]"""
    )
    br_1_6 = CHAPTER(
        SECTION = '1.6',
    title = "Business risks",
    introduction = """Summarize the major business risks associated with developing—or not developing—this product.
Risk categories include marketplace competition, timing issues, user acceptance, implementation
issues, and possible negative impacts on the business. Estimate the potential loss 
from each risk, the likelihood of it occurring, and any potential mitigation actions."""
    )
    br_1_7 = CHAPTER(
        SECTION = '1.7',
    title = "Business assumptions and dependencies",
    introduction = """An assumption is a statement that is believed to be true in the absence of proof or definitive
knowledge. Business assumptions are specifically related to the business requirements. Incorrect
assumptions can potentially keep you from meeting your business objectives. If the new site does not attract enough visitors with a high enough average sale per visitor, the
project might not achieve its business objective. If you learn that certain assumptions are wrong, you
might have to change scope, adjust the schedule, or launch other projects to achieve the objectives."""
    )
    
    BR.add_subchapter(chapter)
    chapter.add_subchapter(br_1_1)
    chapter.add_subchapter(br_1_2)
    chapter.add_subchapter(br_1_3)
    chapter.add_subchapter(br_1_4)
    chapter.add_subchapter(br_1_5)
    chapter.add_subchapter(br_1_6)
    chapter.add_subchapter(br_1_7)
