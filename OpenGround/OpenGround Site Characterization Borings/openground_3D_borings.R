############## THIS SCRIPT CONTAINS CUI ######################################################################
# This script contains a client ID and secret which is equivalent to a username and password.

# title: "Access OpenGround Data - 3D"
# author: "ryan.benac"
# date: 3/13/2025
# you have to query the borings by grid. Query does not return HasDocuments


# Add Libraries
suppressMessages(suppressWarnings({
  library(httr)        # handles GET requests through the API
  library(jsonlite)    # Converts JSON input to df and readable output
  library(dplyr)       # eases data transformation for readability
  library(reshape2)    # reshaping API request
  library(progress)    # for progress bar
  library(stringr)     # extracting text from larger strings
}))


library(jsonlite)

# Load configuration
config_path <- "C:/Workspace/GIT/USACE-AIS-Scripts/config.json"

config <- fromJSON(config_path)


# add useful functions
make_URL <- function(children) {
  return(paste("https://api.eastus.openground.bentley.com/api/v1.0", children, sep=""))
}

# return general query URL
get_query_url <- function() { return("https://api.eastus.openground.bentley.com/api/v1/data/query") }


# Get token 
pull_token <- function() {
  requestTokenURL <- config$og_token_url
  clientID <- config$og_client_id
  clientSecret <- config$og_client_secret
  sandInstID <- config$og_sand_instanceid
  usaceInstID <- config$og_usace_instanceid
  
  body <- list(
    "grant_type" = "client_credentials",
    "scope" = "openground",
    "client_id" = clientID,
    "client_secret" = clientSecret
  )
  
  token_response <- httr::POST(requestTokenURL, body = body, encode = "form")
  
  #interpret_status_code(token_response$status_code)
  
  token <- jsonlite::fromJSON(rawToChar(token_response$content))
  token <- token$access_token
  return(token)
  
}

# make headers for requests
make_headers <- function() {
  token <- pull_token()
  #specified by the API, this is the USACE cloud identifier
  keyCloud <- config$og_keycloud
  
  #specified by the API, in user documentation for OGC API
  instID <- config$og_instanceid
  return(httr::add_headers(
    'KeynetixCLoud' = keyCloud, 
    'Authorization' = paste('Bearer', token), 
    'Content-Type' = 'application/json',
    'InstanceId' = instID,
    'scheme' = 'https'
  ))
}

# make request body for POST to get all project information. Optional to filter by office (full name. MVR use "Rock Island")
make_project_body <- function(filters = NULL) {
  # Add filter if needed
  filterSpec <- list()
  if (!is.null(filters)) {
    filterSpec <- list(list(
      Group = "Office",
      Header = "Name",
      Value = filters,
      Operator = "Contains"
    ))
  }
  
  body_list <- list(
    Projects = NULL,
    Projections = list(),
    Groupings = list(),
    IncludeHasDocuments = TRUE,
    Take = 50000,
    Skip = 0,
    Orderings = list(),
    FilterGroup = list(
      Filters = filterSpec,
      FilterGroups = list(),
      And = TRUE
    ),
    PreFilterGroup = list(
      Filters = list(),
      FilterGroups = list(),
      And = TRUE
    )
  )
  
  json_body <- toJSON(body_list, auto_unbox = TRUE, pretty = TRUE)
  
  return(json_body)
}

# make request body for POST to get all boring information. Need to pass project ID
make_boring_body <- function(projectID) {
  body <- list(
    Projects = list(projectID),
    Projections = list(),
    Groupings = list(),
    IncludeHasDocuments = TRUE,
    Take = 50000,
    Skip = 0,
    Orderings = list(),
    FilterGroup = list(
      Filters = list(),
      FilterGroups = list(),
      And = TRUE
    ),
    PreFilterGroup = list(
      Filters = list(),
      FilterGroups = list(),
      And = TRUE
    )
  )
  json_body <- toJSON(body, auto_unbox = TRUE)
  return(json_body)
}

# make sample information request body for POST to get all sample information. Need to pass project ID
make_depth_body <- function(projectID) {
  sample_info_query <- list(
    Group = "StratumDetails",
    Projects = list(projectID),
    Projections = list(
      list(Group = "StratumDetails", Header = "LocationDetails"),
      list(Group = "StratumDetails", Header = "DepthTop"),
      list(Group = "StratumDetails", Header = "DepthBase"),
      list(Group = "StratumDetails", Header = "Description"),
      list(Group = "StratumDetails", Header = "LegendCode"),
      list(Group = "StratumDetails", Header = "USCS"),
      list(Group = "StratumDetails", Header = "GeologyCode"),
      list(Group = "StratumDetails", Header = "GeologyCode2"),
      list(Group = "StratumDetails", Header = "BoundaryCondition")
    )
  )
  
  json_body <- toJSON(sample_info_query, auto_unbox = TRUE)
  return(json_body)
}


# Function to flatten each entry
flatten_entry <- function(entry) {
  # Extract ID and HasDocuments
  id <- entry[["Id"]]  
  has_documents <- entry[["HasDocuments"]]
  
  # Extract DataFields
  data_fields <- entry[["DataFields"]]  
  
  # Create a data frame from DataFields
  df <- do.call(rbind, apply(data_fields, 1, function(x) {
    data.frame(Header = x[["Header"]], Value = x[["Value"]], stringsAsFactors = FALSE)
  }))
  
  # Reshape data frame so that Headers become columns and Values become their values
  df_wide <- reshape2::dcast(df, . ~ Header, value.var = "Value")
  
  # Add the ID and HasDocuments columns
  df_wide$Id <- id
  df_wide$HasDocuments <- has_documents
  
  return(df_wide)
}


# Function to query all projects from the USACE environment
get_projects <- function(filterQuery = NULL) {
  # break if token is not active
  #if (!check_active()) {
  #  print("Token not active.")
  #  return("Token not active. Exiting function.")
  #}
  #filterQuery = "Rock Island"
  
  
  header <- make_headers()
  accURL <- make_URL("/data/query/grid/d7555a3c-6fe2-4176-ad23-9e77f4216209")
  data <- httr::POST(accURL, header, body = make_project_body(filterQuery))
  
  projects <- jsonlite::fromJSON(rawToChar(data$content))
  
  # Extract entries
  projects <- projects$Entries
  
  # Process into human-readable format
  flat_data <- do.call(rbind, apply(projects, 1, flatten_entry))
  
  # exclude ECHQ projects
  flat_data <- flat_data %>%
    filter(!(Project.ProjectID %in% c("MVR-MISSISSIPPI-DREDGING", "MVR-ILLINOIS-DREDGING")))
  
  
  # add a link to openGround project URL
  flat_data$OpenGround_URL <- paste0("https://webportal.openground.bentley.com/features/locationdetails?projectId=", flat_data$Id, "&projectName=", flat_data$Project.ProjectTitle, "&projectTextId=", flat_data$Project.ProjectID)
  flat_data$OpenGround_URL <- URLencode(flat_data$OpenGround_URL)
  
  return(flat_data)
}


# Function to query all borings for a given project
get_borings <- function(projectID) {
  url <- make_URL("/data/query/grid/210fddd1-227b-471a-a04b-aac60104eafc")
  data <- httr::POST(url, make_headers(), body = make_boring_body(projectID))
  
  borings <- jsonlite::fromJSON(rawToChar(data$content))
  
  # Extract entries
  borings <- borings$Entries
  
  # return empty list if no borings
  if (length(borings) == 0) {
    return(data.frame())
  }
  
  # Apply the function to each entry and combine into a single data frame
  flat_data <- do.call(rbind, apply(borings, 1, flatten_entry))
  
  # add projectID field
  flat_data$Project_ID <- projectID
  
  return(flat_data)
}


# get sample information
get_depth_information <- function(projectID) {
  # for debugging
  #projectID <- "c613f0c4-e46d-4a7a-8e67-f7c9501169d0"
  
  data <- httr::POST(get_query_url(), make_headers(), body = make_depth_body(projectID))
  
  # too much data if you combine raw to Char and fromJSON
  rawchar <- rawToChar(data$content)
  samples <- fromJSON(rawchar)
  
  # return empty list if no borings
  if (length(samples) == 0) {
    return(data.frame())
  }
  
  # Apply the function to each entry and combine into a single data frame
  flat_data <- do.call(rbind, apply(samples, 1, flatten_entry))
  
  # add projectID field
  flat_data$Project_ID <- projectID
  
  return(flat_data)
  
}

get_subsurface_data <- function(filterQuery = NULL) {
  filterQuery = "Rock Island"
  print("Getting projects...")
  projects <- get_projects(filterQuery)
  print("Complete...")
  
  # Rearrange columns and rename
  filteredProjects <- projects %>%
    select(Project_ID = Id, ProjectID = Project.ProjectID, ProjectTitle = Project.ProjectTitle, ProjectLatitude = Project.Latitude, ProjectLongitude = Project.Longitude, ProjectStatus = Project.Status, ProjectEngineer = Project.ProjectEngineer, ProjectCategory = Project.Category, VDatum = Project.VerticalDatum, OpenGround_URL)
  
  # Just get project IDs
  project_ids <- filteredProjects$Project_ID
  
  # Initialize progress bar for the borings query
  pb <- progress_bar$new(
    format = "  Querying borings [:bar] :percent (:current/:total) ETA: :eta",
    total = length(project_ids),
    width = 60
  )
  
  print("Getting borings...")
  # Get all borings and merge together
  full_borings <- do.call(rbind, lapply(project_ids, function(id) {
    pb$tick()  # Update progress bar
    get_borings(id)
  }))
  print("Complete...")
  
  # Select columns and rename as needed
  full_borings <- full_borings %>%
    select(OGC_ID = Id, HasDocuments, Project_ID, LocationID = LocationDetails.LocationID, Type = LocationDetails.LocationType, Status = LocationDetails.Status, Latitude = LocationDetails.LatitudeNumeric, Longitude = LocationDetails.LongitudeNumeric, Date = LocationDetails.DateEnd, TopElevation = LocationDetails.GroundLevel, FinalDepth = LocationDetails.FinalDepth)
  
  
  # Join with project information as a new column
  full_borings <- dplyr::left_join(full_borings, filteredProjects, by = "Project_ID")
  
  # add a document URL if documents exist
  full_borings$Document_URL <- ifelse(
    full_borings$HasDocuments, 
    paste0(
      "https://webportal.openground.bentley.com/features/documents?projectId=",
      full_borings$Project_ID,
      "&queryId=",
      full_borings$OGC_ID,
      "&gridName=Location&entityName=LocationDetails&projectName=",
      full_borings$ProjectID,
      "&itemName=",
      full_borings$OpenGroundLocationID
    ),
    "No records found"
  )
  
  # Initialize progress bar for the borings query
  pb <- progress_bar$new(
    format = "  Querying depth data [:bar] :percent (:current/:total) ETA: :eta",
    total = length(project_ids),
    width = 60
  )
  
  print("Getting depth data...")
  depth_information <- do.call(rbind, lapply(project_ids, function(id) {
    pb$tick()  # Update progress bar
    get_depth_information(id)
  }))
  print("Complete...")
  
  # rename Id and move to front
  depth_information <- depth_information %>%
    select(OGC_ID = StratumDetails.LocationDetails, everything())

  # expand depth_information table by joining full_borings
  borings_with_depth <- dplyr::left_join(depth_information, full_borings, by = "OGC_ID")

  # add district for clarification
  borings_with_depth$District <- "Rock Island District (MVR)"
  
  # select, rename, reorder
  borings_with_depth <- borings_with_depth %>%
    select(LocationID, ProjectID, ProjectTitle, ProjectStatus, LocationType = Type, Status, District, Latitude, Longitude, Date, TopElevation, FinalDepth, StratumTop = StratumDetails.DepthTop, StratumBase = StratumDetails.DepthBase, StratumDetails = StratumDetails.Description, StratumLegend = StratumDetails.LegendCode, StratumUSCS = StratumDetails.USCS, StratumGeology1 = StratumDetails.GeologyCode, StratumGeology2 = StratumDetails.GeologyCode2, StratumBoundary = StratumDetails.BoundaryCondition, OpenGround_URL, Document_URL)
  
  return(borings_with_depth)
}

print("This query takes approximately 10 minutes...")
print("Requesting MVR OpenGround borings for site characterization...")
all_borings <- get_subsurface_data("Rock Island")

print("Validating data...")
# Filter, ensure longitudes are negative, and convert to decimal format
filtered_borings <- all_borings %>%
  filter(!is.na(Longitude) & !is.na(Latitude) & 
           Longitude != 0 & Latitude != 0 & 
           !is.null(Longitude) & !is.null(Latitude)) %>%
  mutate(
    Longitude = as.numeric(ifelse(Longitude > 0, -1 * as.numeric(Longitude), as.numeric(Longitude))),  
    Latitude = as.numeric(Latitude)  
  )





suppressWarnings(library("sf"))
#suppressWarnings(library("arcgisbinding"))

# Convert the dataframe to an sf object
sf_data <- st_as_sf(filtered_borings, coords = c("Longitude", "Latitude"), crs = 4326)

print("Saving as geoJSON...")
# save file
file <- "C:/Workspace/AUTOMATED_SCRIPTS/OpenGround Site Characterization Borings/OUTPUT_GEOJSON/openGround_subsurface_stratum.geojson"
file.remove(file)
st_write(sf_data, file, driver = "GeoJSON", append=FALSE)

print("Complete...")
print("")

