############## THIS SCRIPT CONTAINS CUI CUI CUI CUI CUI CUI CUI CUI ######################################################################
# This script contains a client ID and secret which is equivalent to a username and password.

# title: "Access OpenGround Data"
# author: "ryan.benac"
# date: 9/16/2024

  
  
# Add Libraries
suppressWarnings(library(httr)) # handles GET requests through the API
suppressWarnings(library(jsonlite)) # Converts JSON input to df and readable output
suppressWarnings(library(dplyr)) # eases data transformation for readability
suppressWarnings(library(reshape2)) # reshaping API request
suppressWarnings(library(progress)) # for progress bar

library(jsonlite)

# Load configuration
config_path <- "C:/Workspace/GIT/USACE-AIS-Scripts/config.json"

config <- fromJSON(config_path)

# add useful functions
make_URL <- function(children) {
  wrong <- "https://api.eu-west-2-sandbox.OpenGround.cloud/api/v1.0"
  correct <- "https://api.eastus.openground.bentley.com/api/v1.0"
  return(paste(correct, children, sep=""))
}

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

# return human response to API request
interpret_status_code <- function(code) {
  if (code == 200) {
    cat("Successful Response\n")
  } 
  else if (code == 403) {
    cat("Forbidden Access\n")
  }
  else {
    cat("Unsuccessful Response\n")
  }
}

# checks if token is active. only works with a user token NOT service account
check_active <- function() {
  url <- "https://imsoidc.bentley.com/connect/userinfo"
  data <- httr::GET(url, make_headers())
  response <- NULL
  if (data$status_code == 200) {
    response <- TRUE
  } else {
    response <- FALSE
  }
  return(response)
}

# Function to flatten each entry
flatten_entry <- function(entry) {
  # Extract ID (assuming Id is the first element of the entry)
  id <- entry[["Id"]]  
  
  # Extract DataFields (assuming DataFields is present)
  data_fields <- entry[["DataFields"]]  
  
  # Create a data frame from DataFields
  df <- do.call(rbind, apply(data_fields, 1, function(x) {
    data.frame(Header = x[["Header"]], Value = x[["Value"]], stringsAsFactors = FALSE)
  }))
  
  # Reshape data frame so that Headers become columns and Values become their values
  df_wide <- reshape2::dcast(df, . ~ Header, value.var = "Value")
  
  # Add the ID column
  df_wide$Id <- id
  
  return(df_wide)
}


# Function to query all projects from the USACE environment
get_projects <- function(filterQuery = NULL) {
  # break if token is not active
  #if (!check_active()) {
  #  print("Token not active.")
  #  return("Token not active. Exiting function.")
  #}
  
  header <- make_headers()
  accURL <- make_URL("/data/query/grid/d7555a3c-6fe2-4176-ad23-9e77f4216209")
  data <- httr::POST(accURL, header, body = make_project_body(filterQuery))
  
  projects <- jsonlite::fromJSON(rawToChar(data$content))
  
  # Extract entries
  projects <- projects$Entries
  
  # Process into human-readable format
  flat_data <- do.call(rbind, apply(projects, 1, flatten_entry))
  
  # add a link to openGround project URL
  flat_data$OpenGround_URL <- paste0("https://webportal.openground.bentley.com/features/locationdetails?projectId=", flat_data$Id, "&projectName=", flat_data$Project.ProjectTitle, "&projectTextId=", flat_data$Project.ProjectID)
  
  flat_data$OpenGround_URL <- URLencode(flat_data$OpenGround_URL)
  
  return(flat_data)
}

# Function to query all borings for a given project
get_borings <- function(projectID) {
  # break if token is not active
  #if (!check_active()) {
  #  print("Token not active.")
  #  return("Token not active. Exiting function.")
  #}
  
  # for debugging
  #print(projectID)
  
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

# Use filter to get all borings for a district into a single file
get_multi_project_borings <- function(filter = NULL) {
  filteredProjects <- get_projects(filter)
  
  # Rearrange columns and rename
  filteredProjects <- filteredProjects %>%
    select(Project_ID = Id, ProjectID = Project.ProjectID, ProjectTitle = Project.ProjectTitle, ProjectLatitude = Project.Latitude, ProjectLongitude = Project.Longitude, ProjectStatus = Project.Status, ProjectEngineer = Project.ProjectEngineer, ProjectCategory = Project.Category, VDatum = Project.VerticalDatum, OpenGround_URL)
  
  # Just get project IDs
  project_ids <- filteredProjects$Project_ID
  
  # Initialize progress bar for the borings query
  pb <- progress_bar$new(
    format = "  Querying borings [:bar] :percent (:current/:total) ETA: :eta",
    total = length(project_ids),
    width = 60
  )
  
  # Get all borings and merge together
  full_borings <- do.call(rbind, lapply(project_ids, function(id) {
    pb$tick()  # Update progress bar
    get_borings(id)
  }))
  
  # Select rows and rename as needed
  full_borings <- full_borings %>%
    select(OGC_ID = Id, Project_ID, LocationID = LocationDetails.LocationID, Type = LocationDetails.LocationType, Status = LocationDetails.Status, Latitude = LocationDetails.LatitudeNumeric, Longitude = LocationDetails.LongitudeNumeric, Date = LocationDetails.DateEnd, TopElevation = LocationDetails.GroundLevel, FinalDepth = LocationDetails.FinalDepth)
  
  # Join with project information as a new row
  full_borings <- dplyr::left_join(full_borings, filteredProjects, by = "Project_ID")
  
  # Step 1: Mutate symbology based on Type
  full_borings <- full_borings %>%
    mutate(
      symbology = case_when(
        Type == "BH" ~ "BH",
        TRUE ~ "OTHER"  # Default condition
      )
    )
  
  # Step 2: Overwrite symbology where ProjectID contains "DREDGING"
  full_borings <- full_borings %>%
    mutate(
      symbology = if_else(grepl("DREDGING", ProjectID), "ECHQ Sampling", symbology)
    )
  
  return(full_borings)
}


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


print("Requesting USACE borings...")
all_borings <- get_multi_project_borings()

print("Validating data...")
# Filter, ensure longitudes are negative, and convert to decimal format
filtered_borings <- all_borings %>%
  filter(!is.na(Longitude) & !is.na(Latitude) & Longitude != 0 & Latitude != 0) %>%
  mutate(
    Longitude = as.numeric(ifelse(Longitude > 0, -1*as.numeric(Longitude), as.numeric(Longitude))),  # Set Longitude to negative if it's positive
    Latitude = as.numeric(Latitude)  # Ensure Latitude is numeric/decimal
  )


suppressWarnings(library("sf"))
suppressWarnings(library("arcgisbinding"))

# Convert the dataframe to an sf object
sf_data <- st_as_sf(filtered_borings, coords = c("Longitude", "Latitude"), crs = 4326)

print("Saving as geoJSON...")
# save file
file <- "C:/Workspace/AUTOMATED_SCRIPTS/OpenGround/OUTPUT GEOJSON/openGround_MVR_borings.geojson"
file.remove(file)
st_write(sf_data, file, driver = "GeoJSON", append=FALSE)
