# src/util/doc_template/SoftwareRequirementSpecification/IEEE_template.py
# IEEE 830-compliant SRS template factory.
#
# Outline:
#   Create_SRS_IEEE_Template(authors) → SoftwareRequirementSpecification
#     20 IEEE-830 chapters (Purpose, Scope, Product perspective,
#     Product functions, User characteristics, Constraints,
#     Assumptions, Apportioning, External interfaces, Functions,
#     Usability, Performance, Logical DB, Design constraints,
#     Standards, Software system attributes, Verification, etc.)
#   Create_Chapter_4(SRS, chapter)  populates "Product perspective"
#     with 9 subchapters (System/User/HW/SW/Comm interfaces,
#     Memory, Operations, Site adaptation, Service interfaces).
from util.doc_template.SoftwareRequirementSpecification.SRS import SoftwareRequirementSpecification
from util.doc_template.chapter import CHAPTER

def Create_SRS_IEEE_Template(authors: str) -> SoftwareRequirementSpecification:
    title = "Software Requirement Specification"
    introduction = 'This document outlines the software requirements for the project.'
    SRS =  SoftwareRequirementSpecification(title, introduction, authors)
    chapters_1 = CHAPTER(
        title="SRS overview", SECTION="",
        introduction="""This clause defines the normative content of the software requirements specification (SRS). The project 
shall produce the following information item content in accordance with the project’s policies with 
respect to the software requirements specification. Organization of the content such as the order and 
section structure may be selected in accordance with the project’s information management policies."""
    )
    SRS.add_subchapter(chapters_1)
    chapters_2 = CHAPTER(
        title="Purpose", SECTION="",
        introduction="""Delineate the purpose of the software to be specified."""
    )
    SRS.add_subchapter(chapters_2)
    chapters_3 = CHAPTER(
        title="Scope", SECTION="", # 可变章节
        introduction="""Describe the scope of the software under consideration by:
a) identifying the software product(s) to be produced by name (e.g., Host DBMS, Report Generator, etc.);
b) explaining what the software product(s) will do;
c) describing the application of the software being specified, including relevant benefits, objectives 
and goals; and
d) being consistent with similar statements in higher-level specifications (e.g., a system requirements 
specification), if they exist."""
    )
    SRS.add_subchapter(chapters_3)
    chapters_4 = CHAPTER(
        title="Product perspective", SECTION="",
        introduction="""Define the system's relationship to other related products.
If the product is an element of a larger system, relate the requirements of that larger system to the 
functionality of the product covered by the SRS.
If the product is an element of a larger system, identify the interfaces between the product covered by 
the SRS and the larger system of which the product is an element.
Consider a block diagram showing the major elements of the larger system, interconnections and 
external interfaces.
Describe how the software operates within the following constraints:
a) system interfaces;
b) user interfaces;
c) hardware interfaces;
d) software interfaces;
e) communications interfaces;
f) memory;
g) operations;
h) site adaptation requirements; and
i) interfaces with services."""
    )
    Create_Chapter_4(SRS, chapters_4)
    chapter_5 = CHAPTER(
        title="Product functions", SECTION="",
        introduction="""Provide a summary of the major functions that the software will perform. For example, an SRS for an 
accounting program may use this part to address customer account maintenance, customer statement 
and invoice preparation without mentioning the vast amount of detail that each of those functions requires.
Sometimes the function summary that is necessary for this part can be taken directly from the section 
of the higher-level specification (if one exists) that allocates particular functions to the software 
product.
Use cases, user stories and scenarios are also used to describe product functions.
Note that for the sake of clarity:
a) the product functions should be organized in a way that makes the list of functions understandable 
to the acquirer or to anyone else reading the document for the first time.
b) textual or graphical methods can be used to show the different functions and their relationships. 
Such a diagram is not intended to show a design of a product, but simply shows the logical 
relationships among variables."""
    )
    SRS.add_subchapter(chapter_5)
    chapter_6 = CHAPTER(
        title="User characteristics", SECTION="", # 可变章节
        introduction="""Describe those general characteristics of the intended groups of users of the product including 
characteristics that may influence usability, such as educational level, experience, disabilities and 
technical expertise. This description should not state specific requirements, but rather should state the 
reasons why certain specific requirements are later specified in specific requirements in chapter Apportioning of requirements."""
    )
    SRS.add_subchapter(chapter_6)
    chapter_7 = CHAPTER(
        title="Limitations", SECTION="", # 可变章节
        introduction="""Provide a general description of any other items that will limit the supplier's options, including:
a) regulatory requirements and policies;
b) hardware limitations (e.g., signal timing requirements);
c) interfaces to other applications;
d) parallel operation;
e) audit functions;
f) control functions;
g) higher-order language requirements;
h) signal handshake protocols (e.g., XON-XOFF, ACK-NACK);
i) quality requirements (e.g., reliability);
j) criticality of the application;
k) safety and security considerations;
l) physical/mental considerations; and
m) limitations that are sourced from other systems, including real-time requirements from the 
controlled system through interfaces."""
    )
    SRS.add_subchapter(chapter_7)
    chapter_8 = CHAPTER(
        title="Assumptions and dependencies", SECTION="", # 可变章节
        introduction="""List each of the factors that affect the requirements stated in the SRS. These factors are not design 
constraints on the software but any changes to these factors can affect the requirements in the SRS. 
For example, an assumption may be that a specific operating system will be available on the hardware designated for the software product. If, in fact, the operating system is not available, the SRS would 
have to change accordingly."""
    )
    SRS.add_subchapter(chapter_8)
    chapter_9 = CHAPTER(
        title="Apportioning of requirements", SECTION="", # 可变章节
        introduction="""Apportion the software requirements to software elements. For requirements that will require 
implementation over multiple software elements, or when allocation to a software element is initially 
undefined, this should be so stated. A cross-reference table by function and software element should be 
used to summarize the apportionments.
Identify requirements that may be delayed until future versions of the system (e.g., blocks and/or 
increments)."""
    )
    SRS.add_subchapter(chapter_9)
    chapter_10 = CHAPTER(
        title="Specified requirements", SECTION="", # 可变章节
        introduction="""Specify the software system requirements to a level of detail sufficient for software design, development 
and verification of the software increment or release in process.
The requirements should:
a) be stated in conformance with all the characteristics:
— being with reference to a defined system, software or service;
— enabling an agreed understanding between stakeholders (e.g., acquirers, users, customers, 
operators, suppliers);
— having been validated against real-world needs;
— able to be implemented; and
— providing a reference for verifying designs and solutions.
b) be cross-referenced to earlier versions or related documents;
c) be uniquely identifiable;
d) describe every input (stimulus) into the software system, every output (response) from the 
software system, and all functions performed by the software system in response to an input or in 
support of an output."""
    )
    SRS.add_subchapter(chapter_10)
    chapter_11 = CHAPTER(
        title="External interfaces", SECTION="", # 可变章节
        introduction="""Define all inputs into and outputs from the software system. The description should complement the 
interface descriptions in subchapter System interfaces through subchapter Software interfaces, and should not repeat information there.
Each interface defined should include the following content:
a) name of item;
b) description of purpose;
c) source of input or destination of output;
d) valid range, accuracy and/or tolerance;
e) units of measure;
f) timing;
g) relationships to other inputs/outputs;
h) data formats;
i) command formats; and
j) data items or information included in the input and output."""
    )
    SRS.add_subchapter(chapter_11)
    chapter_12 = CHAPTER(
        title="Functions", SECTION="", # 可变章节
        introduction="""Define the fundamental actions that have to take place in the software in accepting and processing the 
inputs and in processing and generating the outputs, including:
a) validity checks on the inputs;
b) exact sequence of operations;
c) responses to abnormal situations, including:
1) overflow;
2) communication facilities;
3) hardware faults and failures; and
4) error handling and recovery;
d) effect of parameters;
e) relationship of outputs to inputs, including:
1) input/output sequences; and
2) formulas for input to output conversion.
It may be appropriate to partition the functional requirements into sub-functions or sub-processes. 
This does not imply that the software design will also be partitioned that way"""
    )
    SRS.add_subchapter(chapter_12)
    chapter_13 = CHAPTER(
        title="Usability requirements", SECTION="", # 可变章节
        introduction="""Define usability and quality in use requirements and objectives for the software system that can include 
measurable effectiveness, efficiency, satisfaction criteria and avoidance of harm that could arise from 
use in specific contexts of use."""
    )
    SRS.add_subchapter(chapter_13)
    chapter_14 = CHAPTER(
        title="Performance requirements", SECTION="", # 可变章节
        introduction="""Specify both the static and the dynamic numerical requirements placed on the software or on human 
interaction with the software as a whole.
Static numerical requirements may include the following:
a) the number of terminals to be supported;
b) the number of simultaneous users to be supported; and
c) the amount and type of information to be handled.
Static numerical requirements are sometimes identified under a separate section entitled Capacity.
Dynamic numerical requirements may include, for example, the numbers of transactions and tasks and 
the amount of data to be processed within certain time periods for both normal and peak workload 
conditions.
The performance requirements should be stated in measurable terms."""
    )
    SRS.add_subchapter(chapter_14)
    chapter_15 = CHAPTER(
        title="Logical database requirements", SECTION="", # 可变章节
        introduction="""Specify the logical requirements for any information that is to be placed into a database, including:
a) types of information used by various functions;
b) frequency of use;
c) accessing capabilities;
d) data entities and their relationships;
e) integrity constraints;
f) security; and
g) data retention requirements."""
    )
    SRS.add_subchapter(chapter_15)
    chapter_16 = CHAPTER(
        title="Design constraints", SECTION="", # 可变章节
        introduction="""Specify constraints on the system design imposed by external standards, regulatory requirements or 
project limitations."""
    )
    SRS.add_subchapter(chapter_16)
    chapter_17 = CHAPTER(
        title="Standards compliance", SECTION="", # 可变章节
        introduction="""Specify the requirements derived from existing standards or regulations, including:
a) report format;
b) data naming;
c) accounting procedures; and
d) audit tracing.
For example, this could specify the requirement for software to trace processing activity. Such traces 
are needed for some applications to meet minimum regulatory or financial standards. An audit trace 
requirement may, for example, state that all changes to a payroll database shall be recorded in a trace 
file with before and after values."""
    )
    SRS.add_subchapter(chapter_17)
    chapter_18 = CHAPTER(
        title="Software system attributes", SECTION="", # 可变章节
        introduction="""Specify the required attributes of the software product. The following is a partial list of examples:
a) Reliability - specify the factors required to establish the required reliability of the software system 
at the time of delivery.
b) Availability - specify the factors required to guarantee a defined availability level for the entire 
system such as checkpoint, recovery and restart.
c) Security - specify the requirements to protect the software from accidental or malicious access, 
use modification, destruction or disclosure. Specific requirements in this area could include the 
need to:
1) utilize certain cryptographic techniques;
2) keep specific log or history data sets;
3) assign certain functions to different modules;
4) restrict communications between some areas of the programme;
5) check data integrity for critical variables; and
6) assure data privacy;
d) Maintainability - specify attributes of software that relate to the ease of maintenance of the 
software itself. These may include requirements for certain modularity, interfaces or complexity 
limitation. Requirements should not be placed here just because they are thought to be good design 
practices.
e) Portability - specify attributes of software that relate to the ease of porting the software to other 
host machines and/or operating systems, including:
1) percentage of elements with host-dependent code;
2) percentage of code that is host dependent;
3) use of a proven portable language;
4) use of a particular compiler or language subset; and
5) use of a particular operating system."""
    )
    SRS.add_subchapter(chapter_18)
    chapter_19 = CHAPTER(
        title="Verification", SECTION="", # 可变章节
        introduction="""Provide the verification approaches and methods planned to qualify the software. The information 
items for verification are recommended to be given in a parallel manner with the information items in chapter Specified requirements to chapter Software system attributes."""
    )
    SRS.add_subchapter(chapter_19)
    chapter_20 = CHAPTER(
        title="Supporting information", SECTION="", # 可变章节
        introduction="""Additional supporting information to be considered includes:
a) sample input/output formats, descriptions of cost analysis studies or results of user surveys;
b) supporting or background information that can help the readers of the SRS;
c) a description of the problems to be solved by the software; and
d) special packaging instructions for the code and the media to meet security, export, initial loading 
or other requirements.
The SRS should explicitly state whether or not these information items are to be considered part of the 
requirements."""
    )
    SRS.add_subchapter(chapter_20)
    return SRS

def Create_Chapter_4(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): #可变章节
    Chapter_4_1 = CHAPTER(
    title = "System interfaces", SECTION="",
    introduction = """List each system interface and identify the functionality of the software to accomplish the system 
requirement and the interface description to match the system."""
    )
    Chapter_4_2 = CHAPTER(
    title = "User interfaces", SECTION="",
    introduction = """Specify the logical characteristics of each interface between the software product and its users.
NOTE A style guide for the user interface can provide consistent rules for organization, coding and interaction of the user with the system"""
    )
    Chapter_4_3 = CHAPTER(
    title = "Hardware interfaces", SECTION="",
    introduction = """Specify the logical characteristics of each interface between the software product and its users.
NOTE A style guide for the user interface can provide consistent rules for organization, coding and interaction of the user with the system"""
    )
    Chapter_4_4 = CHAPTER(
    title = "Software interfaces", SECTION="",
    introduction = """Specify the use of other required software products (e.g., a data management system, an operating 
system or a mathematical package), and interfaces with other application systems (e.g., the linkage 
between an accounts receivable system and a general ledger system).
For each required software product, specify:
a) name;
b) mnemonic;
c) specification number;
d) version number; and
e) source.
NOTE It is acceptable to specify required platforms or operating systems, but rarely feasible to require a 
specific version. Typically, a version number most recent version or any currently maintain version can be 
specified for software.
For each interface, specify:
a) discussion of the purpose of the interfacing software as related to this software product;
b) definition of the interface in terms of message content and format. It is not necessary to detail any 
well-documented interface, but a reference to the document defining the interface is required."""
    )
    Chapter_4_5 = CHAPTER(
    title = "Communications interfaces", SECTION="",
    introduction = """Specify the various interfaces to communications such as local network protocols."""
    )
    Chapter_4_6 = CHAPTER(
    title = "Memory constraints", SECTION="",
    introduction = """Specify any applicable characteristics and limits on primary and secondary memory."""
    )
    Chapter_4_7 = CHAPTER(
    title = "Operations", SECTION="",
    introduction = """Specify the normal and special operations required by the user such as:
a) the various modes of operations in the user organization (e.g., user-initiated operations);
b) periods of interactive operations and periods of unattended operations;
c) data processing support functions; and
d) backup and recovery operations.
NOTE This is sometimes specified as part of the User Interfaces section."""
    )
    Chapter_4_8 = CHAPTER(
    title = "Site adaptation requirements", SECTION="",
    introduction = """The site adaptation requirements include:
a) definition of the requirements for any data or initialization sequences that are specific to a given 
site, mission or operational mode (e.g., grid values, safety limits, etc.);
b) specification of the site or mission-related features that should be modified to adapt the software 
to a particular installation."""
    )
    Chapter_4_9 = CHAPTER(
    title = "Interfaces with services", SECTION="",
    introduction = """Specify interactions with services, e.g., Software as a Service (SaaS) or cloud services."""
    )
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(Chapter_4_1)
    chapter.add_subchapter(Chapter_4_2)
    chapter.add_subchapter(Chapter_4_3)
    chapter.add_subchapter(Chapter_4_4)
    chapter.add_subchapter(Chapter_4_5)
    chapter.add_subchapter(Chapter_4_6)
    chapter.add_subchapter(Chapter_4_7)
    chapter.add_subchapter(Chapter_4_8)
    chapter.add_subchapter(Chapter_4_9)

