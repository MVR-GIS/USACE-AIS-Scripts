# title: MIDAS_API
# author: Ryan Benac USACE MVR EC-GI
# date last edited: 9/13/2024

# add libraries
suppressWarnings(library(httr)) # handles GET requests through the API
suppressWarnings(library(jsonlite)) # Converts JSON input to df and readable output
suppressWarnings(library(dplyr)) # eases data transformation for readability
suppressWarnings(library(tidyr)) # reshaping dataframe
suppressWarnings(library(stringr)) # helps with text formatting
suppressWarnings(library(lubridate)) # for time reformatting


# Define Functions
# function to return Bearer authorization token. Token must be manually updated every 10 minutes. If you are read only GET the data, you only need to be on the network; no token is needed
pull_token <- function() {
  token <- ""
  return(token)
}

# Create a function to check if latitude and longitude are valid
is_valid_lat_lon <- function(lat, lon) {
  valid_lat <- lat >= -90 & lat <= 90
  valid_lon <- lon >= -180 & lon <= 180
  return(valid_lat & valid_lon)
}

# function to query districts. returns dataframe
get_districts <- function() {
  data <- httr::GET("https://midas.sec.usace.army.mil/api/districts")
  return(jsonlite::fromJSON(rawToChar(data$content)))
}


# function to query projects. returns dataframe
get_projects <- function() {
  data <- httr::GET("https://midas.sec.usace.army.mil/api/projects")
  projects <- jsonlite::fromJSON(rawToChar(data$content))

  # get districts
  districts <- get_districts()

  # join in district infromation
  projects <- projects %>%
    left_join(districts, by = c("district_id" = "id"))


  # select and rename columns
  projects <- projects %>%
    select(project.id = id, project.slug  = slug, project.name = name.x, inst_count = instrument_count, district = name.y, office_code = initials, division = division_name, div_code = division_initials)

  # return result
  return(unique(projects))
}


# function to query all instruments regardless of project. returns dataframe
get_instruments <- function() {
  data <- httr::GET("https://midas.sec.usace.army.mil/api/instruments")
  instruments <- jsonlite::fromJSON(rawToChar(data$content))

  # additional processing to parse out sublist of project
  instruments <- instruments %>%
    unnest_wider(projects, names_sep = "project.")

  # unnest geometry
  instruments <- instruments %>%
    unnest_wider(geometry, names_sep = ".")

  # parse out geometry
  # Create longitude and latitude columns, and rename geometry$coordinates to coords
  instruments <- instruments %>%
    mutate(
      longitude = sapply(geometry.coordinates, `[`, 1),  # Extract first element as longitude
      latitude = sapply(geometry.coordinates, `[`, 2)    # Extract second element as latitude
    )
  instruments <- instruments %>%
    mutate(
      latitude = sapply(longitude, `[`, 2),    # Extract second element as latitude
      longitude = sapply(longitude, `[`, 1)  # Extract first element as longitude
    )

  # add project and district information
  projects <- get_projects()
  instruments <- instruments %>%
    left_join(projects, by = c("projectsproject.id" = "project.id"))

  # rearrange columns and rename
  instruments <- instruments %>%
    select(inst_id = id, inst_slug  = slug, inst_name = name, status, status_time, type, icon, project_slug = projectsproject.slug, project_name = projectsproject.name, nid_id, usgs_id, district, office_code, division, div_code, longitude, latitude)

  # process out empty coordinates or errors
  instruments <- instruments %>%
    filter(!is.na(longitude) & !is.na(latitude) & longitude != 0 & latitude != 0) %>%
    mutate(
      longitude = as.numeric(ifelse(longitude > 0, -1*as.numeric(longitude), as.numeric(longitude))),  # Set Longitude to negative if it's positive
      latitude = as.numeric(latitude)  # Ensure Latitude is numeric/decimal
    )

  # additional processing to remove errors
  instruments <- instruments %>%
    filter(is_valid_lat_lon(latitude, longitude)) %>%  # Keep only rows with valid lat/lon
    mutate(status = stringr::str_to_title(status)) %>%   # Capitalize the 'status' column
    mutate(status_time = if_else(status_time == "0001-01-01T00:00:00Z", NA_character_, status_time))  %>%      # process out any minimum dates
    mutate(status_time = gsub("Z$", "", status_time),          # Remove the 'Z'
           status_time = ymd_hms(status_time),                 # Parse into datetime
           status_time = format(status_time, "%Y-%m-%dT%H:%M:%S")) # Format to desired output

  # reformat the status time
  # Sample column transformation for instruments$status_time
  instruments <- instruments

  # add a column with dashboard URL and instrument URL
  base_url <- "https://midas.sec.usace.army.mil/midas"
  dashboard <- "#dashboard"
  explorer <- "#explorer"

  instruments$dashboardURL <- paste0(base_url, "/", instruments$project_slug, dashboard)
  instruments$explorerURL <- paste0(base_url, "/", instruments$project_slug, explorer)
  instruments$instrumentURL <- paste0(base_url, "/", instruments$project_slug, "/instruments/", instruments$inst_slug)

  return(unique(instruments))
}

print("Requesting instruments from MIDAS")
# get instruments
instruments <- get_instruments()

# MVR Instruments only
#instrumentsMVR  <- instruments %>%
#  filter(office_code == "MVR")

# add columns to support color coded status
instruments$twoStatus <- ifelse(instruments$status =="Active", "Active", "Inactive")

# type to include active
instruments$colorStatus <- paste0(instruments$twoStatus, " ", instruments$twoStatus)

# add library
suppressWarnings(library("sf"))
#suppressWarnings(library("arcgisbinding"))

print("Converting to sf object.")
# Convert the dataframe to an sf object
sf_data <- st_as_sf(instruments, coords = c("longitude", "latitude"), crs = 4326)

print("Saving File")
# save file
file <- "C:/Workspace/AUTOMATED_SCRIPTS/MIDAS/OUTPUT GEOJSON/MIDAS_instruments_ALL.geojson"
file.remove(file)
st_write(sf_data, file, driver = "GeoJSON", append=FALSE)

print("File saved successfully. Exiting program...")
