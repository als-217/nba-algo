#!/usr/bin/env python
# coding: utf-8

# This notebook is for collecting a cleaning data for the model.

# In[2]:


import pandas as pd
import numpy as np
from selenium import webdriver
from csv import writer
import datetime
import time
import html5lib
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from urllib.request import urlopen
from lxml import html
import requests
from bs4 import BeautifulSoup, Comment
import re
from unidecode import unidecode
import nltk
import time
import string
from nltk.tokenize import word_tokenize
nltk.download('punkt')

def isLatin(s):
    try:
        s.encode(encoding='utf-8').decode('ascii')
    except UnicodeDecodeError:
        return False
    else:
        return True
    
def get_season_lineups(season):
    # This function gets all the players that played minutes for every team in a given season.
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('disable-notifications')
    chrome_options.add_argument("window-size=1280,720")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    
    wait = WebDriverWait(driver, 10)
    driver.get("https://www.basketball-reference.com/leagues/NBA_"+str(season)+".html")
    wait.until(EC.element_to_be_clickable((By.XPATH,
                                           '//*[@id="switcher_per_game_team-opponent"]'))).location_once_scrolled_into_view
    table = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="per_game-team"]')))
    teams = [x.get_attribute('href') for x in table.find_elements(By.TAG_NAME, 'a')]
    lineups = []
    for team in teams:
        r = requests.get(team)
        soup = BeautifulSoup(r.text, 'html.parser')
        table = soup.find(id='per_game')
        lineups.append(pd.read_html(table.prettify())[0])
        lineups[len(lineups)-1].iloc[:, 0] = str(team[43:46])
        time.sleep(5)
        
    for lineup in lineups:
        for player in lineup.iloc[:, 1]:
            if isLatin(player) == False:
                player = unidecode(player)
    
    return lineups

def get_lineups(season, month):
    lineups = []
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('disable-notifications')
    chrome_options.add_argument("window-size=1280,720")
    
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    wait = WebDriverWait(driver, 10)
    # Not every season starts/ends in the same month due to Covid. Hence the correct months need to be passed.
    driver.get("https://www.basketball-reference.com/leagues/NBA_"+season+"_games-"+month+".html")

    wait.until(EC.element_to_be_clickable((By.XPATH, '//div[@id="all_schedule"]'))).location_once_scrolled_into_view
    games = wait.until(EC.presence_of_element_located((By.XPATH, '//table[@id="schedule"]')))
    # Getting links to the boxscore of each game
    links = [x.get_attribute('href') for x in games.find_elements(By.TAG_NAME, 'a') if x.text == 'Box Score']
            
    for link in links:
        driver.get(link)
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="line_score"]/tbody/tr[1]/th/a'))).location_once_scrolled_into_view
        teams = [str(driver.find_element(By.XPATH, '//*[@id="line_score"]/tbody/tr[1]/th/a').text),
                 str(driver.find_element(By.XPATH, '//*[@id="line_score"]/tbody/tr[2]/th/a').text)]
        r = requests.get(link)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        for team in teams:
            # Getting boxscore and adding team_id into each dataframe.
            table = soup.find(id="box-"+str(team)+"-game-basic")
            lineups.append(pd.read_html(table.prettify())[0])
            lineups[len(lineups)-1].iloc[5, 0] = team
            lineups[len(lineups)-1].iloc[:, 3] = team
            lineups[len(lineups)-1].iloc[:, 2] = datetime.datetime.strptime(str(driver.find_element(
                By.XPATH, '//*[@id="content"]/div[2]/div[3]/div[1]').text), '%H:%M %p, %B %d, %Y').strftime('%Y-%m-%d') + team
            time.sleep(2)
                
        time.sleep(15)
                
    
    # Some players have letters not in the latin alphabet in their name. The dataset I need to match this to \
    # does not have these letters. Therefore I have to find a remove them. Example: 'Nikola Vučević'
    for lineup in lineups:
        for idx, player in enumerate(lineup.iloc[:, 0]):
            if isLatin(player) == False:
                lineup.iloc[idx, 0] = unidecode(player)
                  
    return lineups

def match_past_raptor(past_lineups, raptor):
    raptor = raptor.loc[raptor['season_type'] == 'RS']
    lineups_dfs = [pd.concat(lineups, axis=0, ignore_index=True) for lineups in past_lineups]
    lineup_df = pd.concat(lineups_dfs, axis=0, ignore_index=True)
    lineup_df.columns = lineup_df.columns.droplevel(0)
    lineup_df.loc[lineup_df.FGA == 'CHO', 'FGA'] = 'CHA'
    
    for idx, player in enumerate(lineup_df.iloc[:, 0]):
        if player in list(raptor.iloc[:, 0]):
            try:
                lineup_df.iloc[idx, 1] = raptor.loc[(raptor['player_name'] == player) & (raptor['team'] == lineup_df.iloc[idx, 3]), 'raptor_total'].item()
            except:
                lineup_df.iloc[idx, 1] = -100
                
    return lineup_df

def get_live_lineups():
    # This function gets all of the projected lineups for today's games.
    players = []
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument('disable-notifications')
    chrome_options.add_argument("window-size=1280,720")
    
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
    wait = WebDriverWait(driver, 10)
    driver.get("https://rotogrinders.com/lineups/nba?site=draftkings")
    driver.find_element(By.XPATH, '//*[@id="bc-close-cookie"]').click()
    driver.find_element(By.XPATH, '//*[@id="top"]/div/section/div/section/div[1]/div[3]/div[1]/div[3]/div/select').click()

    driver.find_element(By.XPATH, '//*[@id="top"]/div/section/div/section/div[1]/div[3]/div[1]/div[3]/div/select/option[2]').click()
    driver.find_element(By.XPATH, '//*[@id="top"]/div/section/div/section/div[1]/div[3]/div[1]/div[3]/div/select/option[1]').click()
    all_ul = driver.find_elements(By.TAG_NAME, 'ul')
    for ul in all_ul:
        all_li = ul.find_elements(By.TAG_NAME, 'li')
        for li in all_li:
            players.append(li.text)
            
    games_teams = [team.find_elements(By.CLASS_NAME, 'shrt') for team in driver.find_elements(By.CLASS_NAME, 'teams')]
    games_teams = [game for game in games_teams if len(game) != 0]
    for game in games_teams:
        for i, team in enumerate(game):
            game[i] = team.get_attribute("innerHTML")
            
    games_teams = [team for game in games_teams for team in game]
    to_keep = ['$', 'Starters', 'Bench']
    current_lineups = []

    for line in players:
        for keep in to_keep:
            if ((line.find(keep) != -1) & (len(line) < 240)):
                current_lineups.append(line)
    
    # Since the lineup data from this website is in an unstructured html table, there is significant superfluous data
    # that needs to be removed.
    # All the lineups are scraped twice so here I remove the second set.
    current_lineups = current_lineups[len(current_lineups)//2:]
    # Removing all punctuation from each player's name.
    current_lineups = [''.join(c for c in player if c not in string.punctuation) for player in current_lineups]
    # Tokenizing each player's name and other information so I can return only the name.
    current_lineups = [word_tokenize(player) for player in current_lineups]
    current_lineups = [token[:3] if len(token) == 6 else token[:2] if len(token) == 5 else token[0] for token in current_lineups]
    current_lineups = [" ".join(player) if type(player) == list else player for player in current_lineups]
    
    index = -1
    for idx, player in enumerate(current_lineups):
        if player == 'Starters':
            index += 1
            
        current_lineups[idx] = {'player': player, 'team': games_teams[index]}
    
    return current_lineups

