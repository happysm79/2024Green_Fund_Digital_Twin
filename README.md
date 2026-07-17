
Ever-GT: Interactive Digital Twin Platform for the Evergreen Terrace Water Distribution System

**Overview**

Ever-GT is an interactive digital twin platform developed through the Southern Illinois University (SIU) Green Fund Project to support sustainable water infrastructure management using hydraulic simulation and web-based visualization.

The platform was developed and demonstrated using the SIU Evergreen Terrace water distribution system as a case study. It integrates EPANET hydraulic models, WNTR simulations, GIS visualization, and an interactive web dashboard to provide an accessible framework for monitoring hydraulic performance, including water pressure, flow conditions, and pipe energy losses. The project emphasizes a modular architecture so that future infrastructure datasets can replace the current proxy model without modifying the core algorithms.

Features

- Interactive web-based dashboard
- EPANET hydraulic simulation
- WNTR-based time-series analysis
- GIS-based network visualization
- Dynamic visualization of
  	- Nodal pressure
		
		- Pipe velocity
		
		- Flow rate
		
		- Unit head loss
		
		- Pipe energy loss
- Interactive map tooltips
- Time-series result tables
- Modular architecture for future digital twin expansion

System Architecture

The framework consists of four major components:

1. Input Network Development

	- GPS survey
	- GIS mapping
	- EPANET model development

2. User Dashboard
	- Upload EPANET (.inp) files
	- Select visualization parameters
	- Select simulation time

3. Hydraulic Engine
	- Flask backend
	- WNTR hydraulic simulation
	- Data processing

4. Interactive Visualization
	- Leaflet.js
	- Dynamic network rendering
	- Interactive parameter visualization

Citation

If you use this repository, please cite:

Ayaluri, V.R. and Shin, S. (2026). Ever-GT: Interactive Digital Twin Platform for the Evergreen Terrace Water Distribution System. Southern Illinois University Green Fund Project.


