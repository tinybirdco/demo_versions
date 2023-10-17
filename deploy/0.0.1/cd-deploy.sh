tb deploy
tb pipe populate events_by_tags_1s_mv__v1 --node mv_1s --wait
tb pipe populate events_by_tags_5m_mv__v1 --node mv_5m --wait
tb pipe populate events_by_tags_15m_mv__v1 --node mv_15m --wait
