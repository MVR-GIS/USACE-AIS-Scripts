############## THIS SCRIPT CONTAINS CUI ######################################################################
# This script contains a client ID and secret which is equivalent to a username and password.

# title: "Access OpenGround Data"
# author: "ryan.benac"
# date: 9/16/2024
# expanded: 2/25/2025 to include SampleInformation query and document query

  
  
# Add Libraries
suppressWarnings(library(httr)) # handles GET requests through the API
suppressWarnings(library(jsonlite)) # Converts JSON input to df and readable output
suppressWarnings(library(dplyr)) # eases data transformation for readability
suppressWarnings(library(reshape2)) # reshaping API request
suppressWarnings(library(progress)) # for progress bar
suppressWarnings(library(stringr)) # extracting text from larger strings

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


# make headers for requests
make_headers <- function() {
  token <- pull_token()
  #specified by the API, this is the USACE cloud identifier
  keyCloud <- "U3VwZXJCYXRtYW5GYXN0"
  
  #specified by the API, in user documentation for OGC API
  instID <- "570c1f2b-aed1-4791-a20b-4b8ac8cdd2c8"
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

# make sample information request body for POST to get all sample information. Need to pass project ID
make_sample_body <- function(projectID) {
  sample_info_query <- list(
    Group = "SampleInformation",
    Projects = list(projectID),
    Projections = list(
      list(Group = "SampleInformation", Header = "DepthTop"),
      list(Group = "SampleInformation", Header = "DepthBase"),
      list(Group = "SampleInformation", Header = "SampleReference"),
      list(Group = "SampleInformation", Header = "Type"),
      list(Group = "SampleInformation", Header = "SampleID"),
      list(Group = "SampleInformation", Header = "DateTimeSampled"),
      list(Group = "SampleInformation", Header = "SampleContainer"),
      list(Group = "SampleInformation", Header = "DepthMidpoint"),
      list(Group = "SampleInformation", Header = "Remarks"),
      list(Group = "SampleInformation", Header = "Description"),
      list(Group = "SampleInformation", Header = "Classification"),
      list(Group = "SampleInformation", Header = "SampleRecordLink"),
      list(Group = "SampleInformation", Header = "uui_LocationDetails")
    )
  )
  
  json_body <- toJSON(sample_info_query, auto_unbox = TRUE)
  return(json_body)
}

# make request body for POST to get all project information. Optional to filter by office (full name. MVR use "Rock Island")
make_project_body <- function() {
  
  body_list <- list(
    Projects = NULL,
    Projections = list(),
    Groupings = list(),
    IncludeHasDocuments = TRUE,
    Take = 50,
    Skip = 0,
    Orderings = list(
      list(
        Group = "Project",
        Header = "ProjectTitle",
        Ascending = TRUE
      )
    ),
    FilterGroup = list(
      Filters = list(),
      FilterGroups = list(
        list(
          Filters = list(),
          FilterGroups = list(
            list(
              Filters = list(
                list(
                  Group = "Project",
                  Header = "ProjectID",
                  Value = "MVR-MISSISSIPPI-DREDGING",
                  Operator = "Contains"
                )
              ),
              FilterGroups = list(),
              And = TRUE
            ),
            list(
              Filters = list(
                list(
                  Group = "Project",
                  Header = "ProjectID",
                  Value = "MVR-ILLINOIS-DREDGING",
                  Operator = "Contains"
                )
              ),
              FilterGroups = list(),
              And = TRUE
            )
          ),
          And = FALSE
        )
      ),
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
get_projects <- function() {
  # break if token is not active
  #if (!check_active()) {
  #  print("Token not active.")
  #  return("Token not active. Exiting function.")
  #}
  
  header <- make_headers()
  accURL <- make_URL("/data/query/grid/d7555a3c-6fe2-4176-ad23-9e77f4216209")
  data <- httr::POST(accURL, header, body = make_project_body())
  
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
  # print(projectID)
  # projectID <- "ed07d33c-672d-4f22-bdb9-be1800d5d827"
  
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
  
  
  # borings should be returned with sample information
  samples <- get_sample_information(projectID)
  
  # join samples with locations
  full_flat <- dplyr::left_join(flat_data, samples, by = c("Id" = "SampleInformation.LocationDetails"))
  
  # add column for count of samples
  full_flat <- full_flat %>%
    dplyr::group_by(Id) %>%
    dplyr::mutate(sampleCount = n()) %>%
    dplyr::ungroup()
  
  # there may be one to many boring to sample. only return samples that say composite
  full_flat <- full_flat %>%
    dplyr::filter(str_to_lower(SampleInformation.SampleReference) == "composite")
  
  return(full_flat)
}

# get sample information
get_sample_information <- function(projectID) {
  # for debugging
   #projectID <- "cb79a389-5408-49c1-bca9-1671c4eb94e5"
  
  data <- httr::POST(get_query_url(), make_headers(), body = make_sample_body(projectID))
  
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

# Use filter to get all borings for a district into a single file
get_multi_project_borings <- function() {
  filteredProjects <- get_projects()
  
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
    select(OGC_ID = Id, HasDocuments = HasDocuments.x, Project_ID = Project_ID.x, OpenGroundLocationID = LocationDetails.LocationID, Type = LocationDetails.LocationType, Status = LocationDetails.Status, Latitude = LocationDetails.LatitudeNumeric, Longitude = LocationDetails.LongitudeNumeric, Date = LocationDetails.DateEnd, TopElevation = LocationDetails.GroundLevel, FinalDepth = LocationDetails.FinalDepth, DredgingEventIdentifier = LocationDetails.Chainage, EventType = LocationDetails.LocationPurpose, RiverMile = LocationDetails.Milemarker, Remarks = LocationDetails.Remarks, DredgingReachName = LocationDetails.SubLocation, SampleDate = SampleInformation.DateTimeSampled, DepthBaseSample = SampleInformation.DepthBase, DepthMidpointSample = SampleInformation.DepthMidpoint, WaterDepth.DepthTop = SampleInformation.DepthTop, DescriptionSample = SampleInformation.Description, RemarksSample = SampleInformation.Remarks, SampleID = SampleInformation.SampleID, SampleReference = SampleInformation.SampleReference, OGC_Sample_ID = Id.y, sampleCount)
  
  # Join with project information as a new row
  full_borings <- dplyr::left_join(full_borings, filteredProjects, by = "Project_ID")
  
  # create URL to navigate to documents related to that boring
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
  
  
  # parse out river
  full_borings$River <- substr(full_borings$OpenGroundLocationID, 1, 2)
  
  # parse out pool
  full_borings$Pool <- substr(full_borings$OpenGroundLocationID, 3, 4)
  
  # Define lookup table as a named vector
  pool_lookup <- c("IL02" = "Lockport",
                   "IL03" = "BR",
                   "IL04" = "DR",
                   "IL05" = "MA",
                   "IL06" = "SR",
                   "IL07" = "PE",
                   "IL08" = "LA",
                   "IL09" = "Alton")
  
  # replace IL river codes based on the first four letters of OpenGroundLocationID
  full_borings <- full_borings %>%
    mutate(Pool = coalesce(pool_lookup[substr(OpenGroundLocationID, 1, 4)], Pool))
  
  
  # parse out channel station. extract second dash and get letter before it
  full_borings$ChannelStation <- ifelse(
    grepl(".*-.*?[A-Za-z]-.*", full_borings$OpenGroundLocationID), 
    sub(".*-.*?([A-Za-z])-.*", "\\1", full_borings$OpenGroundLocationID), 
    ""
  )
  
  # parse out the year from Date 
  full_borings$Year <- sub("^([0-9]{4}).*", "\\1", full_borings$Date)
  
  # overwrite NA in DredgingReach Name with actual null
  full_borings <- full_borings %>%
    mutate(DredgingReachName = na_if(DredgingReachName, "NA"))
  
  # create a more readable sediment sample name
  full_borings$SedimentSampleName <- paste0(full_borings$River, " ", full_borings$RiverMile, full_borings$ChannelStation)
  
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
  
  # convert to numeric
  full_borings$DepthBaseSample <- as.numeric(full_borings$DepthBaseSample)
  full_borings$WaterDepth.DepthTop <- as.numeric(full_borings$WaterDepth.DepthTop)
  
  # fix date and remove time
  full_borings$Date <- as.Date(full_borings$Date)
  
  
  ################################
  # extract additional columns from formatted column
  full_borings$SampleLength <- full_borings$DepthBaseSample - full_borings$WaterDepth.DepthTop
  full_borings$PercentPassing200 <- "Data not yet available"
  full_borings$VisualSedimentDescription <- str_extract(full_borings$RemarksSample, ".*(?=Grain Size:)")
  full_borings$GrainSizeSamplesCount <- str_extract(full_borings$RemarksSample, "(?<=Grain Size: )\\d+")
  full_borings$BulkSamplesCount <- str_extract(full_borings$RemarksSample, "(?<=Bulk Sediment: )\\d+")
  full_borings$ElutriateCount <- str_extract(full_borings$RemarksSample, "(?<=Elutriate: )\\d+")
  full_borings$SiteWaterSamplesCount <- str_extract(full_borings$RemarksSample, "(?<=Site Water: )\\d+")
  full_borings$ChemicalResults <- str_extract(full_borings$RemarksSample, "(?<=Chemical Results: ).*")
  #full_borings$ChemicalResultsLocation <- "Data not yet available"
  
  # replace with NA
  full_borings <- full_borings %>%
    mutate(ChemicalResults = na_if(ChemicalResults, "NA"))
  
  # Capitalize the first letter
  full_borings$VisualSedimentDescription <- str_to_sentence(full_borings$VisualSedimentDescription)
  
  # Remove trailing spaces and a period at the end
  full_borings$VisualSedimentDescription <- gsub("\\.+\\s*$", "", full_borings$VisualSedimentDescription)
  
  
  ################################
  
  
  # reorder so that sediment sample info is together at the beginning
  full_borings <- full_borings %>%
    select(OpenGroundLocationID, SedimentSampleName, River, Pool, ChannelStation, Year, Date, EventType, FinalDepth, DredgingReachName, RiverMile, Remarks, Latitude, Longitude, OpenGround_URL, Document_URL, DredgingEventIdentifier, SampleLength, symbology, countOfOGCSamples = sampleCount, PercentPassing200, VisualSedimentDescription, GrainSizeSamplesCount, BulkSamplesCount, ElutriateCount, SiteWaterSamplesCount, ChemicalResults)
  
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


print("Requesting MVR ECHQ sediment samples...")
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
file <- "C:/Workspace/AUTOMATED_SCRIPTS/OpenGround ECHQ Sediment Samples/OUTPUT GEOJSON/openGround_ECHQ_sediment_data.geojson"
file.remove(file)
st_write(sf_data, file, driver = "GeoJSON", append=FALSE)

