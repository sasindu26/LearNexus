import csv

# Your input data stored as a string
data = """
1. CN Honours Award Project

Topics:

    Project Proposal Development
    Research Methodologies in Networking
    Implementation and Evaluation of Networking Solutions
    Documentation and Presentation Skills
    Reflective Practices in Project Management

2. Platform-Based Development

Topics:

    Overview of Platform Development Concepts
    Frameworks and Tools for Platform Development
    API Development and Integration
    User Experience Design for Platforms
    Monetization Strategies for Platform Solutions

3. Data Warehousing and Data Mining

Topics:

    Fundamentals of Data Warehousing Concepts
    ETL (Extract, Transform, Load) Processes
    Data Mining Techniques and Algorithms
    OLAP (Online Analytical Processing) vs. OLTP (Online Transaction Processing)
    Big Data Technologies and Tools

4. Internet of Things

Topics:

    IoT Architecture and Components
    Sensor Technologies and Data Collection Methods
    Communication Protocols for IoT Devices
    IoT Security Challenges and Solutions
    Smart Device Applications and Use Cases

5. Business Policy and Strategy

Topics:

    Strategic Management Principles
    Business Environment Analysis (PESTEL, SWOT)
    Competitive Strategy Formulation
    Corporate Governance and Ethics
    Policy Implementation and Evaluation

6. Enterprise Networks

Topics:

    Network Architecture and Design Principles
    Network Protocols and Standards
    Security in Enterprise Networks
    Network Management and Monitoring Tools
    Cloud Networking Concepts

7. E-Business Application Development

Topics:

    E-Business Models and Strategies
    Web Application Design and Development
    E-Commerce Technologies and Tools
    Security in E-Business Applications
    Payment Processing and Online Transactions

8. Entrepreneurship

Topics:

    Fundamentals of Entrepreneurship
    Business Idea Generation and Validation
    Business Planning and Strategy
    Funding and Financial Management for Startups
    Marketing Strategies for New Ventures

9. Management Information Systems

Topics:

    Overview of Management Information Systems
    MIS in Decision-Making Processes
    Information Systems Planning and Implementation
    Data Management and Governance
    Evaluating the Effectiveness of MIS

10. Embedded Systems

Topics:

    Introduction to Embedded Systems
    Microcontrollers and Microprocessors
    Embedded System Design and Development
    Real-time Operating Systems
    Applications of Embedded Systems

11. Disaster Recovery and High Availability Techniques

Topics:

    Fundamentals of Disaster Recovery Planning
    Business Continuity Planning
    High Availability Architecture Design
    Backup Strategies and Technologies
    Testing and Maintenance of Disaster Recovery Plans

12. Intrusion Prevention, Detection & Response

Topics:

    Overview of Intrusion Detection Systems (IDS)
    Intrusion Prevention Systems (IPS) and Technologies
    Incident Response Planning
    Threat Analysis and Vulnerability Assessment
    Case Studies in Cybersecurity

13. Parallel and Distributed Computing

Topics:

    Principles of Parallel and Distributed Systems
    Parallel Algorithms and Their Applications
    Distributed Computing Models
    Cloud Computing Concepts
    Performance Measurement and Optimization
"""

# Function to process the string data into a structured format (list of dictionaries)
def parse_data(data):
    modules = []
    current_module = None
    in_topics_section = False

    # Split data by lines
    lines = data.strip().split("\n")

    for line in lines:
        line = line.strip()

        # Check if it's a module (starts with digits followed by a period)
        if line and line[0].isdigit() and "." in line:
            if current_module:  # Save the last module before moving to the new one
                in_topics_section = False  # Reset for the next module
            current_module = line.split('.', 1)[1].strip()  # Extract module name
        
        # Check if it's the start of topics section
        elif line.startswith("Topics:"):
            in_topics_section = True  # Start tracking topics
            continue  # Skip this line
        
        # Capture topics under the current module
        if in_topics_section and line:
            modules.append({"Module": current_module, "Topic": line})  # Add topic to the module

    return modules

# Function to write the parsed data into a CSV file
def write_to_csv(modules, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=["Module", "Topic"])
        writer.writeheader()
        for module in modules:
            writer.writerow(module)

# Parse the string data
modules_data = parse_data(data)

# Write the structured data to a CSV file
write_to_csv(modules_data, 'CN_4.csv')

print("CSV file 'year_4_MIS.csv' has been created successfully!")
