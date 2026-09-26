import {Component} from 'react';
// A failed evidence widget must not take down the officer's entire console.
export default class DecisionBoundary extends Component {
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true};}
 render(){
  if(this.state.failed)return <div role="alert" className="console-notice"><p>This evidence section could not be displayed. Reload the saved evidence or download the report before making a decision.</p><button className="secondary-btn" onClick={()=>this.setState({failed:false})}>Retry this section</button></div>;
  return this.props.children;
 }
}
