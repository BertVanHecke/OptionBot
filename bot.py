from datetime import datetime
from ib_insync import *
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
import nest_asyncio

class Bot:
    """
        Option Bot (Python, Interactive Brokers)
    """

    # Vars
    def __init__(self):
        print("Option bot running, connecting to IB...")

        # Connect to IB
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 7497, clientId=1)
        except Exception as e:
            print(str(e))

        # Create SPY Contract
        self.underlying = Stock("SPY", "SMART", "USD")
        self.ib.qualifyContracts(self.underlying)

        print("Backfilling data to catchup...")

        # Request streaming bars
        self.data = self.ib.reqHistoricalData(self.underlying, endDateTime="", durationStr="2 D",
                                              barSizeSetting="5 mins", whatToShow="TRADES", useRTH=True, keepUpToDate=True)

        # Local vars
        self.in_trade = False

        # Get current options chains
        self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, "", self.underlying.secType, self.underlying.conId)

        # Update chains every hour
        nest_asyncio.apply()
        update_chain_scheduler = BackgroundScheduler(job_defaults={"max_instances": 20})
        update_chain_scheduler.add_job(func=self.update_options_chains, trigger="cron", minute="*")
        update_chain_scheduler.start()

        print("Running live...")

        # Set callback function for streaming bars
        self.data.updateEvent += self.on_bar_update
        self.ib.execDetailsEvent += self.exec_status

        # Run bot forerver
        self.ib.run()




    # Update options chains
    def update_options_chains(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("Updating options chains")

            # Get current options chains
            self.chains = self.ib.reqSecDefOptParams(self.underlying.symbol, "", self.underlying.secType, self.underlying.conId)

        except Exception as e:
            print(str(e))

    #On bar update
    def on_bar_update(self, bars: BarDataList, has_new_bar: bool):
        try:
            if has_new_bar:
                #Convert BarDataList to pandas dataframe
                df = util.df(bars)
                print(df)
                #Check if we are in a trade
                if not self.in_trade:

                    #Insert custom logic here
                    chain = next(c for c in self.chains if c.tradingClass == self.underlying.symbol and c.exchange == self.underlying.exchange)
                    print(chain)
                    strikes = [strike for strike in chain.strikes if strike % 5 == 0 and df.close.iloc[-1] - 10 < strike < df.close.iloc[-1] + 10]
                    expirations = sorted(exp for exp in chain.expirations)[:1]
                    rights = ['P', 'C']

                    contracts = [Option('SPY', expiration, strike, right, 'SMART', tradingClass='SPY')
                        for right in rights
                        for expiration in expirations
                        for strike in strikes]

                    contracts = self.ib.qualifyContracts(*contracts)
                    print("Prepending tickers.. sleeping 15 seconds.")
                    tickers = self.ib.reqTickers(*contracts)
                    self.ib.sleep(15)
                    df = util.df(tickers)
                    print(df)
                    print("Tickers send, returning to main operations.")

        except Exception as e:
            print(str(e))

    #Executing status
    def exec_status(self, trade: Trade, fill: Fill):
        print("Filled")

#Instanciate Class
Bot()
        
