#!/usr/bin/env python3
"""
Create a simple test audio file using text-to-speech
This creates a short conversation for testing
"""

import os

def create_test_audio():
    """Create a test audio file using system TTS"""
    
    # Simple test conversation text
    text = """
    Hello, good morning, Migration Department, this is Rasa speaking, how can I help you today?
Oh hello, yes, good morning, umm, I'm calling because I want to ask about getting Lithuanian passport... I am living here for some years now and, aaa, I think maybe it's time to apply?
Mhm, I understand. May I ask first, are you already a Lithuanian citizen or are you asking about the citizenship process?
No, no, I'm not citizen yet... I'm from Ukraine actually, I have temporary residence permit here... I've been living in Vilnius for, let me think, almost eight years now
Ah okay, so first you would need to obtain Lithuanian citizenship before you can apply for the passport. For naturalization, you need to have lived in Lithuania legally for at least ten years with permanent residence status
Ten years? Oh... mmm, but I have only eight years... and this is with temporary permit, not permanent
Right, so you have a couple of steps ahead. First, you'll need to convert your temporary residence to permanent residence. Have you held the temporary residence continuously?
Yes, yes, continuously... I work here, I have job contract with Lithuanian company, I pay taxes, everything legal
Good, that's very important. After five years of continuous temporary residence, you can apply for permanent residence. Once you have permanent residence and reach ten years total legal residence, then you can apply for citizenship
Okay, okay... so two more years minimum... aaa, what else do I need for citizenship? I heard something about language test?
Mhm, yes, you're right. You need to pass an examination in Lithuanian language and also the fundamentals of the Constitution of the Republic of Lithuania
Oh my... my Lithuanian is okay for work but exam... that sounds difficult
The language requirement is important, yes. You need to demonstrate you can communicate in Lithuanian. There are preparatory courses available if you need them. The Education Development Centre handles the examinations
Mhm, mhm... and what about income? Someone told me there's minimum income requirement?
Yes, correct. You need to show stable income. The current minimum is one thousand thirty-eight euros per month for an adult
Oh, that's fine, I earn more than that... umm, what documents do I need to prepare? There must be many, yes?
Well, let's see... you'll need your birth certificate, translated and apostilled from Ukraine, your current residence permit, employment contract, income statements or bank statements showing your monthly income, criminal record certificate from Ukraine and from Lithuania...
Wow, that's... that's a lot... the criminal record from Ukraine, is that difficult now with the war?
Mmm, yes, I understand it can be challenging given the current situation. We're aware of these difficulties. You might need to work with the Ukrainian embassy here in Vilnius for assistance with obtaining documents from Ukraine
Okay, okay... aaa, once I get citizenship, then passport is easy?
Yes, once you're a citizen, getting the passport is straightforward. You apply through our MIGRIS system or come to our department. The standard processing is one month and costs fifty euros, or if you need urgently, we can do it in one day for hundred forty-three euros
One day? That's fast!
Yes, but only if you submit before noon at the Vilnius department. Otherwise it's next business day
I see, I see... mmm, can my daughter also get citizenship? She's fourteen, she goes to Lithuanian school here
If she's been here with you legally and continuously, yes, she can be included in your naturalization application as your minor child. Actually, children who complete their education in Lithuanian schools often have easier integration
Oh that's good, she speaks Lithuanian better than me actually... teenagers, you know, they learn so fast
laughs Yes, that's often the case. Is there anything specific about the documents you're concerned about?
Well... umm, I'm worried about getting documents from Ukraine... and also, do I need to give up Ukrainian citizenship?
According to the law, generally yes, Lithuania requires renunciation of previous citizenship, but there are some exceptions. Given the current situation with the war, there might be special considerations. I'd recommend consulting with our citizenship division about your specific case
Mhm, I understand... oh, and the exam about Constitution, what is this exactly?
It covers basic knowledge about Lithuanian state structure, main constitutional principles, citizen rights and duties... really fundamental things. There are study materials available
Sounds like I need to study a lot... mmm, how long does the whole process take? From application to getting citizenship?
The citizenship application review officially takes up to six months, but practically it often takes around twelve months, sometimes longer depending on the complexity of the case and document verification
Ah, one year... that's long time to wait
Yes, I understand it seems long, but it's a thorough process. They need to verify all documents, check background, ensure all requirements are met
Okay, okay... umm, where is your office? I think I should come in person maybe to discuss more?
We're at Vytenio street 18 here in Vilnius. You can book an appointment through the MIGRIS system online, or call our general number to schedule
Good, good, I will do that... oh, one more thing, the language exam, when can I take it? Can I take it before ten years?
Actually yes, you can take the exam in advance. Some people prefer to get it done early while they're waiting to reach the ten-year requirement. That way when you're eligible, you already have that requirement completed
Oh, that's smart idea! Maybe I should start preparing now then
That would be wise, yes. Give yourself time to prepare properly. The Education Development Centre website has information about exam dates and preparation materials
Mhm, mhm... thank you so much, you've been very helpful... aaa, actually, sorry, one last question... the fee for citizenship application?
The state fee for the citizenship application is currently eighty-six euros and seventy cents
Okay, not too bad... well, thank you very much, really, this helps a lot to understand the process
You're very welcome! Don't hesitate to call again if you have more questions. Good luck with your application when the time comes
Thank you, thank you... have a nice day!
You too, goodbye!
Bye bye!Retry
    """
    
    # Use macOS 'say' command to create audio (works on Mac)
    if os.system("which say > /dev/null 2>&1") == 0:
        print("Using macOS 'say' command to generate test audio...")
        os.system(f'say -o test_audio.aiff "{text}"')
        
        # Convert to WAV if possible
        if os.system("which ffmpeg > /dev/null 2>&1") == 0:
            print("Converting to WAV format...")
            os.system("ffmpeg -i test_audio.aiff -acodec pcm_s16le -ar 16000 test_audio.wav -y")
            os.remove("test_audio.aiff")
            print("✅ Created test_audio.wav")
        else:
            print("✅ Created test_audio.aiff (install ffmpeg to convert to WAV)")
    else:
        print("⚠️ 'say' command not found (not on macOS)")
        print("Please provide your own audio file")
        print("\nYou can:")
        print("1. Record a short audio with your phone/computer")
        print("2. Download a sample audio from the internet")
        print("3. Use any .wav, .mp3, or .m4a file")
        print("\nName it 'test_audio.wav' and place it in this directory")

if __name__ == "__main__":
    create_test_audio()