# src/util/doc_template/SoftwareRequirementSpecification/Initial_template.py
# Basic 7-chapter SRS template factory.
#
# Outline:
#   Create_SRS_Initial_Template(authors) → SoftwareRequirementSpecification
#     7 chapters: Introduction, Overall description, System features,
#     Data requirements, External interface requirements, Quality attributes,
#     Other requirements.
#   Create_Introduction / Create_Overall_Description / Create_System_Features /
#   Create_Data_Requirements / Create_EIR / Create_Quality_Attributes /
#   Create_Other_Requirements   subchapter populators (called in top factory).
from util.doc_template.SoftwareRequirementSpecification.SRS import SoftwareRequirementSpecification
from util.doc_template.chapter import CHAPTER

# 增加从案例到模板的工具

# 每个大步骤都是四个大类，不同的产出对于不同的借口（上下文图....）,不同的分析技巧也可以作为不同的参数



def Create_SRS_Initial_Template(authors: str) -> SoftwareRequirementSpecification:
    title = "Software Requirement Specification"
    introduction = 'This document outlines the software requirements for the project.'
    SRS =  SoftwareRequirementSpecification(title, introduction, authors)
    chapters_1 = CHAPTER(
        title="Introduction", SECTION="1",
        introduction="The introduction presents an overview to help the reader understand how the SRS is organized and how to use it."
    )
    Create_Introduction(SRS, chapters_1)
    chapters_2 = CHAPTER(
        title="Overall description", SECTION="",
        introduction="This section presents a high-level overview of the product and the environment in which it will be used, the anticipated users, and known constraints, assumptions, and dependencies."
    )
    Create_Overall_Description(SRS, chapters_2)
    chapters_3 = CHAPTER(
        title="System features", SECTION="",
        introduction="This section enumerates the detailed requirements for the system."
    )
    Create_System_Features(SRS, chapters_3)
    chapters_4 = CHAPTER(
        title="Data requirements", SECTION="",
        introduction="Information systems provide value by manipulating data. Use this section of the template to describe various aspects of the data that the system will consume as inputs, process in some fashion, or create as outputs. "
    )
    Create_Data_Requirements(SRS, chapters_4)
    chapter_5 = CHAPTER(
        title="External interface requirements", SECTION="",
        introduction="""This section provides information to ensure that the system will communicate properly with users and
with external hardware or software elements. Reaching agreement on external and internal system
interfaces has been identified as a software industry best practice (Brown 1996). A complex system
with multiple subcomponents should create a separate interface specification or system architecture
specification. The interface documentation could incorporate material from other documents by
reference. For instance, it could point to a hardware device manual that lists the error codes that the
device could send to the software."""
    )
    Create_EIR(SRS, chapter_5)
    chapter_6 = CHAPTER(
        title="Quality attributes", SECTION="",
        introduction="""Nonfunctional requirements specify criteria that can be used to judge the operation of a system,
rather than specific behaviors. They include aspects such as performance, security, usability, and
reliability. Nonfunctional requirements often apply to the system as a whole, rather than to
individual features or services. They might also affect the development process itself, such as coding
standards or quality metrics."""
    )
    Create_Quality_Attributes(SRS, chapter_6)
    chapter_7 = CHAPTER(
        title="Other requirements", SECTION="",
        introduction="""Define any other requirements that are not covered elsewhere in the SRS. Examples are legal,
regulatory, or financial compliance and standards requirements; requirements for product installation,
configuration, startup, and shutdown; and logging, monitoring, and audit trail requirements. Instead
of just combining these all under “Other,” add any new sections to the template that are pertinent
to your project. Omit this section if all your requirements are accommodated in other sections.
Transition requirements that are necessary for migrating from a previous system to a new one could
be included here if they involve software being written (as for data conversion programs), or in the
project management plan if they do not (as for training development or delivery)."""
    )
    Create_Other_Requirements(SRS, chapter_7)
    return SRS

def Create_Other_Requirements(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): #可变章节
    other_7_1 = CHAPTER(
    title = "Legal and regulatory requirements", SECTION="",
    introduction = """Specify any legal or regulatory requirements that the product must comply with. These could include
data protection regulations, industry-specific standards, accessibility laws, and intellectual property
considerations. Identify the specific laws, regulations, or standards that apply and describe how the
product will meet these requirements."""
    )
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(other_7_1)

def Create_Quality_Attributes(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): #可变章节
    qa_6_1 = CHAPTER(
    title = "Usability", SECTION="",
    introduction = """Usability requirements deal with ease of learning, ease of use, error avoidance and recovery, efficiency
of interactions, and accessibility. The usability requirements specified here will help the user interface
designer create the optimum user experience."""
    )
    qa_6_2 = CHAPTER(
    title = "Reliability", SECTION="",
    introduction = """State specific performance requirements for various system operations. If different functional
requirements or features have different performance requirements, it’s appropriate to specify those
performance goals right with the corresponding functional requirements, rather than collecting them
in this section."""
    )
    qa_6_3 = CHAPTER(
    title = "Security", SECTION="",
    introduction = """Specify any requirements regarding security or privacy issues that restrict access to or use of the
product. These could refer to physical, data, or software security. Security requirements often
originate in business rules, so identify any security or privacy policies or regulations to which the
product must conform. If these are documented in a business rules repository, just refer to them."""
    )
    qa_6_4 = CHAPTER(
    title = "Safety", SECTION="",
    introduction = """Specify requirements that are concerned with possible loss, damage, or harm that could result
from use of the product. Define any safeguards or actions that must be taken, as well as potentially
dangerous actions that must be prevented. Identify any safety certifications, policies, or regulations to
which the product must conform."""
    )
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(qa_6_1)
    chapter.add_subchapter(qa_6_2)
    chapter.add_subchapter(qa_6_3)
    chapter.add_subchapter(qa_6_4)

def Create_EIR(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): 
    eir_5_1 = CHAPTER(
    title = "User interfaces", SECTION="",
    introduction = """Describe the logical characteristics of each user interface that the system needs. Some specific
characteristics of user interfaces could appear in section 6.1 Usability. Some possible items to address
here are:
- References to user interface standards or product line style guides that are to be followed
- Standards for fonts, icons, button labels, images, color schemes, field tabbing sequences,
commonly used controls, branding graphics, copyright and privacy notices, and the like
- Screen size, layout, or resolution constraints
- Standard buttons, functions, or navigation links that will appear on every screen, such as a
help button
- Shortcut keys
- Message display and phrasing conventions
- Data validation guidelines (such as input value restrictions and when to validate field contents)
- Layout standards to facilitate software localization
- Accommodations for users who are visually impaired, color blind, or have other limitations
"""
    )
    eir_5_2 = CHAPTER(
    title = "Hardware interfaces", SECTION="",
    introduction = """Describe the characteristics of each interface between the software components and hardware
components, if any, of the system. This description might include the supported device types, the data
and control interactions between the software and the hardware, and the communication protocols
to be used. List the inputs and outputs, their formats, their valid values or ranges, and any timing
issues developers need to be aware of. If this information is extensive, consider creating a separate
interface specification document. For more about specifying requirements for systems containing
hardware."""
    )
    eir_5_3 = CHAPTER(
    title = "Software interfaces", SECTION="",
    introduction = """Describe the connections between this product and other software components (identified by name
and version), including other applications, databases, operating systems, tools, libraries, websites, and
integrated commercial components. State the purpose, formats, and contents of the messages, data,
and control values exchanged between the software components. Specify the mappings of input and
output data between the systems and any translations that need to be made for the data to get from
one system to the other. Describe the services needed by or from external software components and
the nature of the inter-component communications. Identify data that will be exchanged between or
shared across software components. Specify nonfunctional requirements affecting the interface, such
as service levels for response times and frequencies, or security controls and restrictions."""
    )
    eir_5_4 = CHAPTER(
    title = "Communication interfaces", SECTION="",
    introduction = """State the requirements for any communication functions the product will use, including email, web
browser, network protocols, and electronic forms. Define any pertinent message formatting. Specify
communication security and encryption issues, data transfer rates, handshaking, and synchronization
mechanisms. State any constraints around these interfaces, such as whether certain types of email
attachments are acceptable or not."""
    )
    
    SRS.add_subchapter(chapter)   
    chapter.add_subchapter(eir_5_1)
    chapter.add_subchapter(eir_5_2)
    chapter.add_subchapter(eir_5_3)
    chapter.add_subchapter(eir_5_4)

def Create_Data_Requirements(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): 
    data_4_1 = CHAPTER(
    title = "Logical data model", SECTION="",
    introduction = """a data model is a visual representation of the data objects and collections
the system will process and the relationships between them. Numerous notations exist for data
modeling, including entity-relationship diagrams and UML class diagrams. You might include a data
model for the business operations being addressed by the system, or a logical representation for the
data that the system will manipulate. This is not the same thing as an implementation data model that
will be realized in the form of database design."""
    )
    data_4_2 = CHAPTER(
    title = "Data dictionary", SECTION="",
    introduction = """The data dictionary defines the composition of data structures and the meaning, data type, length,
format, and allowed values for the data elements that make up those structures. Commercial data
modeling tools often include a data dictionary component. In many cases, you’re better off storing
the data dictionary as a separate artifact, rather than embedding it in the middle of an SRS. That also
increases its reusability potential in other projects. """
    ) 
    data_4_3 = CHAPTER(
    title = "Reports", SECTION="",
    introduction = """If your application will generate any reports, identify them here and describe their characteristics.
If a report must conform to a specific predefined layout, you can specify that here as a constraint,
perhaps with an example. Otherwise, focus on the logical descriptions of the report content, sort
sequence, totaling levels, and so forth, deferring the detailed report layout to the design stage."""
    )
    data_4_4 = CHAPTER(
    title = "Data dictionary", SECTION="",
    introduction = """If relevant, describe how data is acquired and maintained. For instance, when starting a data
inventory feed, you might need to do an initial dump of all the inventory data to the receiving system
and then have subsequent feeds that consist only of changes. State any requirements regarding the
need to protect the integrity of the system’s data. Identify any specific techniques that are necessary,
such as backups, checkpointing, mirroring, or data accuracy verification. State policies the system
must enforce for either retaining or disposing of data, including temporary data, metadata, residual
data (such as deleted records), cached data, local copies, archives, and interim backups."""
    ) 
    
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(data_4_1)
    chapter.add_subchapter(data_4_2)
    chapter.add_subchapter(data_4_3)
    chapter.add_subchapter(data_4_4)



def Create_System_Features(SRS: SoftwareRequirementSpecification, chapter: CHAPTER): # 可变章节
    feature_3_1 = CHAPTER(
    title = "System feature 1", SECTION="",
    introduction = """ Can have several features and corresponding sections.
    This chapter should provide a short description of the feature and indicate whether it is of high, medium, or low priority. Priorities often are dynamic,
    changing over the course of the project. Also need to Itemize the specific functional requirements associated with this feature. These are the software
    capabilities that must be implemented for the user to carry out the feature’s services or to perform a use case. 
    Describe how the product should respond to anticipated error conditions and to invalid inputs and actions. Uniquely label each functional requirement, as described earlier in this chapter."""
    )
    
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(feature_3_1)


def Create_Overall_Description(SRS: SoftwareRequirementSpecification, chapter: CHAPTER):
    chapters_2_1 = CHAPTER(
    title = "Product perspective", SECTION="",
    introduction = """Describe the product’s context and origin. Is it the next member of a growing product line, the next
version of a mature system, a replacement for an existing application, or an entirely new product? If
this SRS defines a component of a larger system, state how this software relates to the overall system
and identify major interfaces between the two. Consider including visual models such as a context
diagram or ecosystem map to show the product’s relationship to other
systems."""
    )
    chapters_2_2 = CHAPTER(
    title = "User classes and characteristics", SECTION="",
    introduction = """Identify the various user classes that you anticipate will use this product, and describe their pertinent
characteristics. Some requirements might pertain only to certain user classes. Identify the favored user classes. User classes represent a subset of the
stakeholders described in the vision and scope document. User class descriptions are a reusable
resource. If a master user class catalog is available, you can incorporate user class descriptions by
simply pointing to them in the catalog instead of duplicating information here."""
    )
    chapters_2_3 = CHAPTER(
    title = "Operating environment", SECTION="",
    introduction = """Describe the environment in which the software will operate, including the hardware platform;
operating systems and versions; geographical locations of users, servers, and databases; and
organizations that host the related databases, servers, and websites. List any other software
components or applications with which the system must peacefully coexist. If extensive technical
infrastructure work needs to be performed in conjunction with developing the new system, consider
creating a separate infrastructure requirements specification to detail that work."""
    )
    chapters_2_4 = CHAPTER(
    title = "Design and implementation constraints", SECTION="",
    introduction = """There are times when a certain programming language must be used, a particular code library that
has already had time invested to develop it needs to be used, and so forth. Describe any factors
that will restrict the options available to the developers and the rationale for each constraint.
Requirements that incorporate or are written in the form of solution ideas rather than needs are
imposing design constraints, often unnecessarily, so watch out for those. Constraints are described
further in Chapter 14, “Beyond functionality.”"""
    )
    chapters_2_5 = CHAPTER(
    title = "Assumptions and dependencies", SECTION="",
    introduction = """An assumption is a statement that is believed to be true in the absence of proof or definitive
knowledge. Problems can arise if assumptions are incorrect, are obsolete, are not shared, or change,
so certain assumptions will translate into project risks. One SRS reader might assume that the product
will conform to a particular user interface convention, whereas another might assume something
different. A developer might assume that a certain set of functions will be custom-written for this
application, whereas the business analyst might assume that they will be reused from a previous
project, and the project manager might expect to procure a commercial function library. The
assumptions to include here are those related to system functionality; business-related assumptions
appear in the vision and scope document
Identify any dependencies the project or system being built has on external factors or components
outside its control. For instance, if Microsoft .NET Framework 4.5 or a more recent version must be
installed before your product can run, that’s a dependency."""
    )
    SRS.add_subchapter(chapter)  
    chapter.add_subchapter(chapters_2_1)
    chapter.add_subchapter(chapters_2_2) 
    chapter.add_subchapter(chapters_2_3)
    chapter.add_subchapter(chapters_2_4)
    chapter.add_subchapter(chapters_2_5)     

def Create_Introduction(SRS: SoftwareRequirementSpecification, chapter: CHAPTER):
    chapters_1_1 = CHAPTER(
    title = "Introduction", SECTION="",
    introduction = """Identify the product or application whose requirements are specified in this document, including the
    revision or release number. If this SRS pertains to only part of a complex system, identify that portion
    or subsystem. Describe the different types of reader that the document is intended for, such as
    developers, project managers, marketing staff, users, testers, and documentation writers."""
    )
    chapters_1_2 = CHAPTER(
    title = "Document conventions", SECTION="",
    introduction = """Describe any standards or typographical conventions used, including the meaning of specific text
styles, highlighting, or notations. If you are manually labeling requirements, you might specify the
format here for anyone who needs to add one later."""
    )
    chapters_1_3 = CHAPTER(
    title = "Project scope", SECTION="",
    introduction = """Provide a short description of the software being specified and its purpose. Relate the software to
user or corporate goals and to business objectives and strategies. If a separate vision and scope or
similar document is available, refer to it rather than duplicating its contents here. An SRS that specifies
an incremental release of an evolving product should contain its own scope statement as a subset of
the long-term strategic product vision. You might provide a high-level summary of the major features
the release contains or the significant functions that it performs."""
    )
    chapters_1_4 = CHAPTER( 
    title = "References", SECTION="",
    introduction = """List any documents or other resources to which this SRS refers. Include hyperlinks to them if they are
in a persistent location. These might include user interface style guides, contracts, standards, system
requirements specifications, interface specifications, or the SRS for a related product. Provide enough
information so that the reader can access each reference, including its title, author, version number,
date, source, storage location, or URL."""
    )
    
    SRS.add_subchapter(chapter)
    chapter.add_subchapter(chapters_1_1)
    chapter.add_subchapter(chapters_1_2)
    chapter.add_subchapter(chapters_1_3)
    chapter.add_subchapter(chapters_1_4)

