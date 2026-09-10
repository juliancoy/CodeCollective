-- Provision the standalone timebank tenant in the existing org database.
-- Keep it separate from both the main portal and Bmore Timebank.
INSERT INTO timebank_communities (id, hostname, name, tagline, accent_color)
VALUES (
  'timebank',
  'timebank.codecollective.us',
  'Code Collective Timebank',
  'Good neighbors. Useful skills. Time well shared.',
  '#155e59'
)
ON CONFLICT(id) DO NOTHING;
