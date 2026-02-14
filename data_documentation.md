The data files in the data folder are from the Muuttolintujen kevät public data set:

- `mlk-public-data.txt` is the full data set with tens of millions of records (7 GB)
- `mlk-public-data-10k.txt` is a 10k sample
- `mlk-public-data-100.txt` is a 100 sample

Each row is a record of a bird species occurrence.

##Columns:

- species: species scientific name (string or empty)
- prediction: probability of the species identification (0-1) adjusted by species distibution model, 2 decimal places, (float or empty)
- orig_prediction: probability of the species identification without the species distibution model, 10+ decimal places, (float or empty)
- song_start: position of the vocalication from recording start, in seconds, (integer or empty)
- rec_id: recording ID, (UUID or empty)
- result_id: result ID, (UUID or empty)
- feedback: whether the user provided feedback on the recording, (boolean or empty)
- isseen: whether the user saw the species, (boolean or empty)
- isheard: whether the user heard the species, (boolean or empty)
- user_anon: anonymized user ID, (UUID or empty)
- time: recording timestamp, ISO 8601 (string or empty)
- len: recording length (?), (integer or empty)
- dur: recording duration in seconds, (integer or empty)
- real_obs: whether the user reported the recording as a real observation, (boolean or empty)
- rec_type: recording type, (string "direct", "interval", "point" or empty)
- point_count_loc: point count location name, (string or empty)
- year: year of the recording, (integer or empty)
- lat: latitude of the recording, (float or empty)
- lon: longitude of the recording, (float or empty)
- data_generalization: data generalization level, (integer or empty)

## Example:

species	prediction	orig_prediction	song_start	rec_id	result_id	feedback	isseen	isheard	user_anon	time	len	dur	real_obs	rec_type	point_count_loc	year	lat	lon	data_generalization
Sylvia communis	0.36	0.359282818202371	40	78a81605-7088-4f5c-aa98-2200f674643f	4c5f8b07-914e-4ff8-bab3-162d52922624				user_175662	2025-05-16T11:43:27.235000	382024	46.5882926829268	TRUE	direct		2025	61.677	29.645	1

